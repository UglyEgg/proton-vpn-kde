// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "SecretTransport.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QTest>

#include <fcntl.h>
#include <memory>
#include <openssl/evp.h>
#include <unistd.h>

namespace
{
using PKey = std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>;
using PKeyContext = std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)>;

QByteArray backendPublicKey()
{
    PKeyContext context(EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, nullptr),
                        EVP_PKEY_CTX_free);
    EVP_PKEY *generatedKey = nullptr;
    if (!context
        || EVP_PKEY_keygen_init(context.get()) <= 0
        || EVP_PKEY_keygen(context.get(), &generatedKey) <= 0) {
        return {};
    }
    PKey key(generatedKey, EVP_PKEY_free);
    QByteArray publicKey(32, '\0');
    size_t size = static_cast<size_t>(publicKey.size());
    if (EVP_PKEY_get_raw_public_key(
            key.get(), reinterpret_cast<unsigned char *>(publicKey.data()),
            &size) <= 0
        || size != 32) {
        return {};
    }
    return publicKey;
}
}

class SecretTransportTest final : public QObject
{
    Q_OBJECT

private slots:
    void createsReadableSealedPayload();
};

void SecretTransportTest::createsReadableSealedPayload()
{
    QString errorMessage;
    const QByteArray publicKey = backendPublicKey();
    QCOMPARE(publicKey.size(), 32);
    const QDBusUnixFileDescriptor descriptor = SecretTransport::createSealedPayload(
        {{QStringLiteral("username"), QStringLiteral("demo")},
         {QStringLiteral("password"), QStringLiteral("correct horse")}},
        publicKey,
        &errorMessage);

    QVERIFY2(descriptor.isValid(), qPrintable(errorMessage));
    const int fd = descriptor.fileDescriptor();
    QVERIFY(fd >= 0);

    const int seals = ::fcntl(fd, F_GET_SEALS);
    QVERIFY(seals >= 0);
    QVERIFY(seals & F_SEAL_SEAL);
    QVERIFY(seals & F_SEAL_SHRINK);
    QVERIFY(seals & F_SEAL_GROW);
    QVERIFY(seals & F_SEAL_WRITE);

    QByteArray payload(1024, '\0');
    const ssize_t bytesRead = ::read(fd, payload.data(), payload.size());
    QVERIFY(bytesRead > 0);
    payload.truncate(bytesRead);
    QCOMPARE(static_cast<unsigned char>(payload.front()), 1);
    QVERIFY(!payload.contains("demo"));
    QVERIFY(!payload.contains("correct horse"));
    payload.fill('\0');
}

QTEST_GUILESS_MAIN(SecretTransportTest)

#include "SecretTransportTest.moc"
