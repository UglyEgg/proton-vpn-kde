// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "SecretTransport.h"

#include <QByteArray>
#include <QCoreApplication>
#include <QJsonObject>
#include <QString>

#include <cstdio>
#include <unistd.h>

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    if (application.arguments().size() != 2) {
        std::fputs("usage: secret-transport-vector PUBLIC_KEY_BASE64\n", stderr);
        return 2;
    }

    const QByteArray publicKey = QByteArray::fromBase64(
        application.arguments().at(1).toLatin1(),
        QByteArray::AbortOnBase64DecodingErrors);
    QString errorMessage;
    const QDBusUnixFileDescriptor descriptor =
        SecretTransport::createSealedPayload(
            {{QStringLiteral("username"), QStringLiteral("interop-user")},
             {QStringLiteral("password"), QStringLiteral("interop-password")}},
            publicKey,
            &errorMessage);
    if (!descriptor.isValid()) {
        std::fprintf(stderr, "%s\n", qPrintable(errorMessage));
        return 1;
    }

    QByteArray encrypted;
    char buffer[4096];
    for (;;) {
        const ssize_t bytesRead = ::read(
            descriptor.fileDescriptor(), buffer, sizeof(buffer));
        if (bytesRead < 0) {
            std::perror("read");
            return 1;
        }
        if (bytesRead == 0) {
            break;
        }
        encrypted.append(buffer, bytesRead);
    }

    const QByteArray encoded = encrypted.toBase64();
    encrypted.fill('\0');
    if (std::fwrite(encoded.constData(), 1,
                    static_cast<size_t>(encoded.size()), stdout)
        != static_cast<size_t>(encoded.size())) {
        std::perror("write");
        return 1;
    }
    std::fputc('\n', stdout);
    return 0;
}
