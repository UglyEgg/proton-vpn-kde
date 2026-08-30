// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "ConnectionAction.h"
#include "DbusContract.h"
#include "SecretTransport.h"

#include <QClipboard>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QGuiApplication>
#include <QJsonObject>
#include <QRegularExpression>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;

bool normalizeServerFeatures(const QStringList &features, QStringList *result)
{
    static const QStringList supported{
        QStringLiteral("p2p"),
        QStringLiteral("streaming"),
        QStringLiteral("tor"),
        QStringLiteral("secure-core"),
    };
    if (!result || features.size() > supported.size()) {
        return false;
    }
    QStringList requested;
    for (const QString &feature : features) {
        const QString normalized = feature.trimmed().toLower();
        if (!supported.contains(normalized)) {
            return false;
        }
        if (!requested.contains(normalized)) {
            requested.append(normalized);
        }
    }
    result->clear();
    for (const QString &feature : supported) {
        if (requested.contains(feature)) {
            result->append(feature);
        }
    }
    return true;
}
}

void VpnController::activatePrimaryAction()
{
    if (!primaryActionEnabled()) {
        return;
    }
    if (m_state == QStringLiteral("connecting")) {
        callControlOperation(QString::fromLatin1(BackendDbus::Method::disconnect));
        return;
    }
    const bool shouldDisconnect = ProtonVpnKde::primaryActionDisconnects(m_state);
    if (shouldDisconnect) {
        callOperation(QString::fromLatin1(BackendDbus::Method::disconnect));
    } else {
        callFastestOperation(m_fastestFeatures);
    }
}

void VpnController::disconnect()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || m_state == QStringLiteral("disconnected")) {
        return;
    }
    callControlOperation(QString::fromLatin1(BackendDbus::Method::disconnect));
}

void VpnController::copyForwardedPort()
{
    if (m_forwardedPort <= 0) {
        return;
    }
    if (QClipboard *clipboard = QGuiApplication::clipboard()) {
        clipboard->setText(QString::number(m_forwardedPort));
    }
}

void VpnController::startPacketCapture(const QString &directoryPath)
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_busy
        || m_state != QStringLiteral("connected") || m_packetCaptureActive) {
        return;
    }
    const QString normalized = directoryPath.trimmed();
    if (normalized.isEmpty() || normalized.size() > 4096
        || normalized.contains(QLatin1Char('\n'))
        || normalized.contains(QLatin1Char('\r'))) {
        m_message = tr("Select a valid packet-capture folder");
        emit snapshotChanged();
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::startPacketCapture), {normalized});
}

void VpnController::stopPacketCapture()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_busy
        || !m_packetCaptureActive) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::stopPacketCapture));
}

void VpnController::submitSupportReport(const QString &username,
                                        const QString &email,
                                        const QString &description,
                                        bool includeLogs)
{
    if (!supportReportSubmissionEnabled()) {
        emit supportReportFinished(
            false,
            tr("Direct Proton support submission is disabled in this unofficial community build"));
        return;
    }
    const QString normalizedUsername = username.trimmed();
    const QString normalizedEmail = email.trimmed();
    const QString normalizedDescription = description.trimmed();
    static const QRegularExpression emailPattern(
        QRegularExpression::anchoredPattern(
            QStringLiteral("[^@\\s]+@[^@\\s]{2,}\\.[^@\\s.\\-]{2,}")));
    QString validationMessage;
    if (normalizedUsername.isEmpty() || normalizedUsername.size() > 255
        || normalizedUsername.contains(QLatin1Char('\0'))) {
        validationMessage = tr("Enter your Proton username");
    } else if (normalizedEmail.size() > 254
               || normalizedEmail.contains(QLatin1Char('\0'))
               || !emailPattern.match(normalizedEmail).hasMatch()) {
        validationMessage = tr("Enter a valid email address");
    } else if (normalizedDescription.contains(QLatin1Char('\0'))
               || normalizedDescription.size() < 50) {
        validationMessage = tr("Describe the issue using at least 50 characters");
    } else if (normalizedDescription.size() > 8000) {
        validationMessage = tr("The issue description is too long");
    }
    if (!validationMessage.isEmpty()) {
        emit supportReportFinished(false, validationMessage);
        return;
    }
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_busy) {
        emit supportReportFinished(
            false, tr("Sign in and wait for the current VPN operation to finish"));
        return;
    }

    const QJsonObject fields{
        {QStringLiteral("username"), normalizedUsername},
        {QStringLiteral("email"), normalizedEmail},
        {QStringLiteral("description"), normalizedDescription},
        {QStringLiteral("includeLogs"),
         includeLogs ? QStringLiteral("true") : QStringLiteral("false")},
    };
    const QString backendDestination = m_backendDestination;
    const quint64 backendGeneration = m_backendGeneration;
    QDBusMessage keyRequest = QDBusMessage::createMethodCall(
        backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getAuthPublicKey));
    keyRequest << QString::fromLatin1(BackendDbus::Method::submitSupportReport);
    auto *keyWatcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(keyRequest, 5000), this);
    connect(keyWatcher, &QDBusPendingCallWatcher::finished, this,
            [this, fields, backendDestination, backendGeneration](
                QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QString> keyReply = *finished;
        finished->deleteLater();
        if (keyReply.isError()
            || backendGeneration != m_backendGeneration
            || backendDestination != m_backendDestination) {
            emit supportReportFinished(
                false, tr("Unable to protect the issue report"));
            return;
        }

        QString errorMessage;
        const QByteArray publicKey = QByteArray::fromBase64(
            keyReply.value().toLatin1());
        const QDBusUnixFileDescriptor descriptor =
            SecretTransport::createSealedPayload(fields, publicKey, &errorMessage);
        if (!descriptor.isValid()) {
            emit supportReportFinished(
                false, tr("Unable to protect the issue report"));
            return;
        }

        QDBusMessage reportRequest = QDBusMessage::createMethodCall(
            backendDestination,
            QString::fromLatin1(BackendDbus::objectPath),
            QString::fromLatin1(BackendDbus::interfaceName),
            QString::fromLatin1(BackendDbus::Method::submitSupportReport));
        reportRequest << QVariant::fromValue(descriptor);
        auto *reportWatcher = new QDBusPendingCallWatcher(
            QDBusConnection::sessionBus().asyncCall(reportRequest, 120000), this);
        connect(reportWatcher, &QDBusPendingCallWatcher::finished, this,
                [this](QDBusPendingCallWatcher *reportFinished) {
            const QDBusPendingReply<> reportReply = *reportFinished;
            reportFinished->deleteLater();
            if (reportReply.isError()) {
                refresh();
                emit supportReportFinished(
                    false, tr("The issue report could not be submitted"));
                return;
            }
            refresh();
            emit supportReportFinished(
                true, tr("Your issue has been reported"));
        });
    });
}

void VpnController::connectCountry(const QString &countryCode)
{
    if (primaryActionEnabled()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectCountry), {countryCode});
    }
}

void VpnController::connectCountryWithFeatures(
    const QString &countryCode, const QStringList &features)
{
    QStringList normalized;
    if (primaryActionEnabled()
        && normalizeServerFeatures(features, &normalized)) {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectCountryWithFeatures),
            {countryCode, QVariant::fromValue(normalized)});
    }
}

void VpnController::connectTarget(const QString &target)
{
    if (!primaryActionEnabled()) {
        return;
    }
    const QString normalized = target.trimmed().toUpper();
    if (normalized == QStringLiteral("FASTEST")) {
        callFastestOperation(m_fastestFeatures);
    } else if (normalized.contains(QLatin1Char('#'))) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectServer), {normalized});
    } else if (!normalized.isEmpty()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectCountry), {normalized});
    }
}

void VpnController::connectFastestWithFeature(const QString &feature)
{
    connectFastestWithFeatures({feature});
}

void VpnController::connectFastestWithFeatures(const QStringList &features)
{
    if (primaryActionEnabled()) {
        callFastestOperation(features);
    }
}

void VpnController::connectGroup(const QString &countryCode,
                                 const QString &groupKind,
                                 const QString &groupName)
{
    if (primaryActionEnabled()) {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectGroup),
            {countryCode, groupKind, groupName});
    }
}

void VpnController::connectGroupWithFeatures(
    const QString &countryCode, const QString &groupKind,
    const QString &groupName, const QStringList &features)
{
    QStringList normalized;
    if (primaryActionEnabled()
        && normalizeServerFeatures(features, &normalized)) {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectGroupWithFeatures),
            {countryCode, groupKind, groupName,
             QVariant::fromValue(normalized)});
    }
}

void VpnController::connectServer(const QString &serverName)
{
    if (primaryActionEnabled()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectServer), {serverName});
    }
}

void VpnController::login(const QString &username, const QString &password)
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy) {
        return;
    }
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::login),
        {{QStringLiteral("username"), username},
         {QStringLiteral("password"), password}});
}

void VpnController::submitTwoFactor(const QString &code)
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy) {
        return;
    }
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitTwoFactor),
        {{QStringLiteral("code"), code}});
}

void VpnController::cancelLogin()
{
    callOperation(QString::fromLatin1(BackendDbus::Method::cancelLogin));
}

void VpnController::beginFido2()
{
    callOperation(QString::fromLatin1(BackendDbus::Method::beginFido2));
}

void VpnController::submitFido2Pin(const QString &pin)
{
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitFido2Pin),
        {{QStringLiteral("pin"), pin}},
        false);
}

void VpnController::cancelFido2()
{
    callControlOperation(QString::fromLatin1(BackendDbus::Method::cancelFido2));
}

void VpnController::logout()
{
    callOperation(QString::fromLatin1(BackendDbus::Method::logout));
}

void VpnController::disableKillSwitchForLogin()
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy
        || m_killSwitch == 0) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::disableKillSwitchForLogin));
}

void VpnController::setReconnectionEnabled(bool enabled)
{
    m_reconnectionEnabled = enabled;
    if (!m_backendAvailable) {
        return;
    }
    callControlOperation(
        QString::fromLatin1(BackendDbus::Method::setReconnectionEnabled),
        {enabled});
}

void VpnController::setFastestFeatures(const QStringList &features)
{
    QStringList normalized;
    if (normalizeServerFeatures(features, &normalized)) {
        m_fastestFeatures = normalized;
    }
}

void VpnController::callOperation(const QString &method,
                                  const QVariantList &arguments)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        return;
    }
    m_busy = true;
    m_message.clear();
    emit snapshotChanged();

    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleOperationReply);
}

void VpnController::callFastestOperation(const QStringList &features)
{
    QStringList normalized;
    if (!normalizeServerFeatures(features, &normalized)) {
        return;
    }
    if (normalized.isEmpty()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectFastest));
    } else {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectFastestWithFeatures),
            {QVariant::fromValue(normalized)});
    }
}

void VpnController::callSecretOperation(const QString &method,
                                        const QJsonObject &fields,
                                        bool updateBusy)
{
    if (updateBusy) {
        m_busy = true;
        m_message.clear();
        emit snapshotChanged();
    }

    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        if (updateBusy) {
            m_busy = false;
        }
        m_message = tr("The Proton backend is not available");
        emit snapshotChanged();
        return;
    }
    const QString backendDestination = m_backendDestination;
    const quint64 backendGeneration = m_backendGeneration;
    QDBusMessage keyRequest = QDBusMessage::createMethodCall(
        backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getAuthPublicKey));
    keyRequest << method;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(keyRequest, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, method, fields, updateBusy, backendDestination,
             backendGeneration](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QString> reply = *finished;
        finished->deleteLater();
        if (reply.isError()
            || backendGeneration != m_backendGeneration
            || backendDestination != m_backendDestination) {
            if (updateBusy) {
                m_busy = false;
            }
            m_message = tr("Unable to initialize protected authentication");
            emit snapshotChanged();
            return;
        }

        QString errorMessage;
        const QByteArray publicKey = QByteArray::fromBase64(reply.value().toLatin1());
        const QDBusUnixFileDescriptor descriptor =
            SecretTransport::createSealedPayload(fields, publicKey, &errorMessage);
        if (!descriptor.isValid()) {
            if (updateBusy) {
                m_busy = false;
            }
            m_message = tr("Unable to protect the authentication data: %1")
                            .arg(errorMessage);
            emit snapshotChanged();
            return;
        }

        QDBusMessage request = QDBusMessage::createMethodCall(
            backendDestination, QString::fromLatin1(BackendDbus::objectPath),
            QString::fromLatin1(BackendDbus::interfaceName), method);
        request << QVariant::fromValue(descriptor);
        auto *operationWatcher = new QDBusPendingCallWatcher(
            QDBusConnection::sessionBus().asyncCall(request, 120000), this);
        connect(operationWatcher, &QDBusPendingCallWatcher::finished, this,
                updateBusy ? &VpnController::handleOperationReply
                           : &VpnController::handleControlOperationReply);
    });
}

void VpnController::callControlOperation(const QString &method,
                                         const QVariantList &arguments)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleControlOperationReply);
}
