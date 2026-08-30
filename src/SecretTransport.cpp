#include "SecretTransport.h"

#include <QByteArray>
#include <QJsonDocument>

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <openssl/evp.h>
#include <openssl/kdf.h>
#include <openssl/rand.h>
#include <string_view>
#include <sys/mman.h>
#include <unistd.h>

namespace
{
constexpr unsigned char kPayloadVersion = 1;
constexpr qsizetype kPublicKeySize = 32;
constexpr qsizetype kNonceSize = 12;
constexpr qsizetype kTagSize = 16;
constexpr std::string_view kKdfInfo = "proton-vpn-kde-auth-v1";
constexpr std::string_view kAdditionalData =
    "quest.entropy.PlasmaVPN.Backend1";

using PKey = std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>;
using PKeyContext = std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)>;
using CipherContext = std::unique_ptr<EVP_CIPHER_CTX, decltype(&EVP_CIPHER_CTX_free)>;

void setError(QString *errorMessage, const QString &message)
{
    if (errorMessage) {
        *errorMessage = message;
    }
}

QByteArray deriveKey(EVP_PKEY *privateKey, EVP_PKEY *peerKey)
{
    PKeyContext deriveContext(EVP_PKEY_CTX_new(privateKey, nullptr),
                              EVP_PKEY_CTX_free);
    if (!deriveContext
        || EVP_PKEY_derive_init(deriveContext.get()) <= 0
        || EVP_PKEY_derive_set_peer(deriveContext.get(), peerKey) <= 0) {
        return {};
    }

    size_t sharedSize = 0;
    if (EVP_PKEY_derive(deriveContext.get(), nullptr, &sharedSize) <= 0) {
        return {};
    }
    QByteArray shared(static_cast<qsizetype>(sharedSize), '\0');
    if (EVP_PKEY_derive(
            deriveContext.get(),
            reinterpret_cast<unsigned char *>(shared.data()),
            &sharedSize) <= 0) {
        shared.fill('\0');
        return {};
    }
    shared.resize(static_cast<qsizetype>(sharedSize));

    PKeyContext hkdf(EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr),
                     EVP_PKEY_CTX_free);
    QByteArray key(32, '\0');
    size_t keySize = static_cast<size_t>(key.size());
    const bool derived = hkdf
        && EVP_PKEY_derive_init(hkdf.get()) > 0
        && EVP_PKEY_CTX_hkdf_mode(
               hkdf.get(), EVP_PKEY_HKDEF_MODE_EXTRACT_AND_EXPAND) > 0
        && EVP_PKEY_CTX_set_hkdf_md(hkdf.get(), EVP_sha256()) > 0
        && EVP_PKEY_CTX_set1_hkdf_key(
               hkdf.get(),
               reinterpret_cast<const unsigned char *>(shared.constData()),
               static_cast<int>(shared.size())) > 0
        && EVP_PKEY_CTX_add1_hkdf_info(
               hkdf.get(),
               reinterpret_cast<const unsigned char *>(kKdfInfo.data()),
               kKdfInfo.size()) > 0
        && EVP_PKEY_derive(
               hkdf.get(), reinterpret_cast<unsigned char *>(key.data()),
               &keySize) > 0;
    shared.fill('\0');
    if (!derived || keySize != 32) {
        key.fill('\0');
        return {};
    }
    return key;
}

QByteArray encrypt(const QByteArray &plaintext, const QByteArray &backendPublicKey)
{
    if (backendPublicKey.size() != kPublicKeySize) {
        return {};
    }

    PKeyContext keygenContext(EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, nullptr),
                              EVP_PKEY_CTX_free);
    EVP_PKEY *generatedKey = nullptr;
    if (!keygenContext
        || EVP_PKEY_keygen_init(keygenContext.get()) <= 0
        || EVP_PKEY_keygen(keygenContext.get(), &generatedKey) <= 0) {
        return {};
    }
    PKey ephemeralKey(generatedKey, EVP_PKEY_free);
    PKey peerKey(
        EVP_PKEY_new_raw_public_key(
            EVP_PKEY_X25519, nullptr,
            reinterpret_cast<const unsigned char *>(backendPublicKey.constData()),
            static_cast<size_t>(backendPublicKey.size())),
        EVP_PKEY_free);
    if (!peerKey) {
        return {};
    }

    QByteArray ephemeralPublicKey(kPublicKeySize, '\0');
    size_t publicKeySize = static_cast<size_t>(ephemeralPublicKey.size());
    if (EVP_PKEY_get_raw_public_key(
            ephemeralKey.get(),
            reinterpret_cast<unsigned char *>(ephemeralPublicKey.data()),
            &publicKeySize) <= 0
        || publicKeySize != static_cast<size_t>(kPublicKeySize)) {
        return {};
    }

    QByteArray key = deriveKey(ephemeralKey.get(), peerKey.get());
    if (key.size() != 32) {
        return {};
    }
    QByteArray nonce(kNonceSize, '\0');
    if (RAND_bytes(
            reinterpret_cast<unsigned char *>(nonce.data()), nonce.size()) != 1) {
        key.fill('\0');
        return {};
    }

    CipherContext context(EVP_CIPHER_CTX_new(), EVP_CIPHER_CTX_free);
    QByteArray ciphertext(plaintext.size() + EVP_MAX_BLOCK_LENGTH, '\0');
    int ciphertextSize = 0;
    int outputSize = 0;
    const bool initialized = context
        && EVP_EncryptInit_ex(context.get(), EVP_aes_256_gcm(), nullptr,
                              nullptr, nullptr) > 0
        && EVP_CIPHER_CTX_ctrl(
               context.get(), EVP_CTRL_GCM_SET_IVLEN, nonce.size(), nullptr) > 0
        && EVP_EncryptInit_ex(
               context.get(), nullptr, nullptr,
               reinterpret_cast<const unsigned char *>(key.constData()),
               reinterpret_cast<const unsigned char *>(nonce.constData())) > 0
        && EVP_EncryptUpdate(
               context.get(), nullptr, &outputSize,
               reinterpret_cast<const unsigned char *>(kAdditionalData.data()),
               static_cast<int>(kAdditionalData.size())) > 0
        && EVP_EncryptUpdate(
               context.get(),
               reinterpret_cast<unsigned char *>(ciphertext.data()),
               &outputSize,
               reinterpret_cast<const unsigned char *>(plaintext.constData()),
               plaintext.size()) > 0;
    key.fill('\0');
    if (!initialized) {
        ciphertext.fill('\0');
        return {};
    }
    ciphertextSize = outputSize;
    if (EVP_EncryptFinal_ex(
            context.get(),
            reinterpret_cast<unsigned char *>(ciphertext.data()) + ciphertextSize,
            &outputSize) <= 0) {
        ciphertext.fill('\0');
        return {};
    }
    ciphertextSize += outputSize;
    ciphertext.resize(ciphertextSize);

    QByteArray tag(kTagSize, '\0');
    if (EVP_CIPHER_CTX_ctrl(
            context.get(), EVP_CTRL_GCM_GET_TAG, tag.size(), tag.data()) <= 0) {
        ciphertext.fill('\0');
        return {};
    }

    QByteArray result;
    result.reserve(1 + ephemeralPublicKey.size() + nonce.size()
                   + ciphertext.size() + tag.size());
    result.append(static_cast<char>(kPayloadVersion));
    result.append(ephemeralPublicKey);
    result.append(nonce);
    result.append(ciphertext);
    result.append(tag);
    return result;
}

bool writeAll(int descriptor, const QByteArray &payload)
{
    qsizetype written = 0;
    while (written < payload.size()) {
        const ssize_t result = ::write(
            descriptor,
            payload.constData() + written,
            static_cast<size_t>(payload.size() - written));
        if (result < 0 && errno == EINTR) {
            continue;
        }
        if (result <= 0) {
            return false;
        }
        written += result;
    }
    return true;
}
}

QDBusUnixFileDescriptor SecretTransport::createSealedPayload(
    const QJsonObject &fields, const QByteArray &backendPublicKey,
    QString *errorMessage)
{
    if (!QDBusUnixFileDescriptor::isSupported()) {
        setError(errorMessage, QStringLiteral("Unix file-descriptor passing is unavailable"));
        return {};
    }

    QByteArray plaintext = QJsonDocument(fields).toJson(QJsonDocument::Compact);
    QByteArray encrypted = encrypt(plaintext, backendPublicKey);
    plaintext.fill('\0');
    if (encrypted.isEmpty()) {
        setError(errorMessage, QStringLiteral("Credential encryption failed"));
        return {};
    }

    const int descriptor = ::memfd_create(
        "proton-vpn-kde-auth",
        MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (descriptor < 0) {
        encrypted.fill('\0');
        setError(errorMessage, QString::fromLocal8Bit(std::strerror(errno)));
        return {};
    }

    if (!writeAll(descriptor, encrypted)) {
        const QString message = QString::fromLocal8Bit(std::strerror(errno));
        encrypted.fill('\0');
        ::close(descriptor);
        setError(errorMessage, message);
        return {};
    }
    encrypted.fill('\0');

    constexpr int seals = F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE;
    if (::fcntl(descriptor, F_ADD_SEALS, seals) < 0
        || ::lseek(descriptor, 0, SEEK_SET) < 0) {
        const QString message = QString::fromLocal8Bit(std::strerror(errno));
        ::close(descriptor);
        setError(errorMessage, message);
        return {};
    }

    QDBusUnixFileDescriptor result;
    result.giveFileDescriptor(descriptor);
    return result;
}
