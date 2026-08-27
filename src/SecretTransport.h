#pragma once

#include <QDBusUnixFileDescriptor>
#include <QJsonObject>
#include <QString>

class QByteArray;

namespace SecretTransport
{
[[nodiscard]] QDBusUnixFileDescriptor createSealedPayload(
    const QJsonObject &fields, const QByteArray &backendPublicKey,
    QString *errorMessage = nullptr);
}
