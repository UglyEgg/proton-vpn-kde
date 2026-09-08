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

bool authenticationRecoveryRequired(const QString &authState)
{
    return authState == QStringLiteral("authentication_unknown")
        || authState == QStringLiteral("expired")
        || authState == QStringLiteral("account_restart_required")
        || authState == QStringLiteral("settings_unavailable")
        || authState == QStringLiteral("protection_unknown");
}

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

QString connectionTargetState(const QString &method)
{
    if (method == QString::fromLatin1(BackendDbus::Method::disconnect)) {
        return QStringLiteral("disconnected");
    }
    if (method == QString::fromLatin1(BackendDbus::Method::connectCountry)
        || method == QString::fromLatin1(
            BackendDbus::Method::connectCountryWithFeatures)
        || method == QString::fromLatin1(BackendDbus::Method::connectFastest)
        || method == QString::fromLatin1(
            BackendDbus::Method::connectFastestWithFeatures)
        || method == QString::fromLatin1(BackendDbus::Method::connectGroup)
        || method == QString::fromLatin1(
            BackendDbus::Method::connectGroupWithFeatures)
        || method == QString::fromLatin1(BackendDbus::Method::connectServer)) {
        return QStringLiteral("connected");
    }
    return {};
}

QVariant packetCaptureTargetActive(const QString &method)
{
    if (method == QString::fromLatin1(BackendDbus::Method::startPacketCapture)) {
        return true;
    }
    if (method == QString::fromLatin1(BackendDbus::Method::stopPacketCapture)) {
        return false;
    }
    return {};
}
}

void VpnController::activatePrimaryAction()
{
    if (!primaryActionEnabled()) {
        return;
    }
    if (primaryActionDisconnects()) {
        disconnect();
    } else {
        callFastestOperation(m_fastestFeatures);
    }
}

void VpnController::disconnect()
{
    if (!canDisconnect()) {
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
    if (!m_backendAvailable || !m_ready || !m_loggedIn || !snapshotHealthy()
        || m_busy
        || m_state != QStringLiteral("connected") || m_packetCaptureActive) {
        return;
    }
    m_packetCaptureStopRequested = false;
    const QString normalized = directoryPath.trimmed();
    if (normalized.isEmpty() || normalized.size() > 4096
        || normalized.contains(QLatin1Char('\n'))
        || normalized.contains(QLatin1Char('\r'))) {
        m_message = tr("Select a valid packet-capture folder");
        m_packetCaptureExpectedActive.reset();
        m_packetCaptureError = m_message;
        emit snapshotChanged();
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::startPacketCapture), {normalized});
}

void VpnController::stopPacketCapture()
{
    if (m_packetCaptureOperationPending
        && m_packetCaptureExpectedActive.has_value()
        && !*m_packetCaptureExpectedActive) {
        return;
    }
    if (!m_packetCaptureStopRequested && !m_shutdownPending
        && !m_packetCaptureActive
        && (!m_packetCaptureExpectedActive.has_value()
            || !*m_packetCaptureExpectedActive)) {
        return;
    }
    m_packetCaptureError.clear();
    m_packetCaptureStopRequested = true;
    dispatchPendingPacketCaptureStop();
}

void VpnController::dispatchPendingPacketCaptureStop(bool allowUnconfirmedActive)
{
    if (!m_packetCaptureStopRequested) {
        return;
    }
    if (m_packetCaptureOperationPending
        && m_packetCaptureExpectedActive.has_value()
        && !*m_packetCaptureExpectedActive) {
        return;
    }
    if (!m_backendAvailable || !m_ready) {
        return;
    }
    if (!m_packetCaptureError.isEmpty() && !allowUnconfirmedActive) {
        return;
    }
    const bool startMayStillActivate =
        m_packetCaptureExpectedActive.has_value()
        && *m_packetCaptureExpectedActive;
    if (!m_packetCaptureActive && !startMayStillActivate
        && !allowUnconfirmedActive) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::stopPacketCapture));
}

bool VpnController::requestShutdown()
{
    const bool cleanupRequired = m_packetCaptureActive
        || m_packetCaptureOperationPending || m_packetCaptureStopRequested
        || (m_packetCaptureExpectedActive.has_value()
            && *m_packetCaptureExpectedActive);
    if (!cleanupRequired) {
        return true;
    }
    if (!m_shutdownPending) {
        m_shutdownPending = true;
        emit snapshotChanged();
    }
    stopPacketCapture();
    return false;
}

void VpnController::completeShutdownIfSafe()
{
    if (!m_shutdownPending) {
        return;
    }
    const bool cleanupRequired = m_packetCaptureActive
        || m_packetCaptureOperationPending || m_packetCaptureStopRequested
        || (m_packetCaptureExpectedActive.has_value()
            && *m_packetCaptureExpectedActive);
    if (cleanupRequired) {
        return;
    }
    m_shutdownPending = false;
    emit snapshotChanged();
    emit shutdownReady();
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
    if (!m_backendAvailable || !m_ready || !m_loggedIn || !snapshotHealthy()
        || m_busy) {
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
    stampBackendRequest(keyWatcher);
    connect(keyWatcher, &QDBusPendingCallWatcher::finished, this,
            [this, fields, backendDestination, backendGeneration](
                QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QString> keyReply = *finished;
        const bool current = backendReplyIsCurrent(finished);
        finished->deleteLater();
        if (!current
            || backendGeneration != m_backendGeneration
            || backendDestination != m_backendDestination) {
            return;
        }
        if (keyReply.isError()) {
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
        stampBackendRequest(reportWatcher);
        connect(reportWatcher, &QDBusPendingCallWatcher::finished, this,
                [this](QDBusPendingCallWatcher *reportFinished) {
            const QDBusPendingReply<> reportReply = *reportFinished;
            const bool current = backendReplyIsCurrent(reportFinished);
            reportFinished->deleteLater();
            if (!current) {
                return;
            }
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
    if (canConnect()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectCountry), {countryCode});
    }
}

void VpnController::connectCountryWithFeatures(
    const QString &countryCode, const QStringList &features)
{
    QStringList normalized;
    if (canConnect()
        && normalizeServerFeatures(features, &normalized)) {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectCountryWithFeatures),
            {countryCode, QVariant::fromValue(normalized)});
    }
}

void VpnController::connectTarget(const QString &target)
{
    if (!canConnect()) {
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
    if (canConnect()) {
        callFastestOperation(features);
    }
}

void VpnController::connectGroup(const QString &countryCode,
                                 const QString &groupKind,
                                 const QString &groupName)
{
    if (canConnect()) {
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
    if (canConnect()
        && normalizeServerFeatures(features, &normalized)) {
        callOperation(
            QString::fromLatin1(BackendDbus::Method::connectGroupWithFeatures),
            {countryCode, groupKind, groupName,
             QVariant::fromValue(normalized)});
    }
}

void VpnController::connectServer(const QString &serverName)
{
    if (canConnect()) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectServer), {serverName});
    }
}

void VpnController::login(const QString &username, const QString &password)
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy
        || authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::login),
        {{QStringLiteral("username"), username},
         {QStringLiteral("password"), password}});
}

void VpnController::submitTwoFactor(const QString &code)
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy
        || authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitTwoFactor),
        {{QStringLiteral("code"), code}});
}

void VpnController::cancelLogin()
{
    if (authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::cancelLogin));
}

void VpnController::beginFido2()
{
    if (authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::beginFido2));
}

void VpnController::submitFido2Pin(const QString &pin)
{
    if (authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitFido2Pin),
        {{QStringLiteral("pin"), pin}},
        false);
}

void VpnController::cancelFido2()
{
    if (authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callControlOperation(QString::fromLatin1(BackendDbus::Method::cancelFido2));
}

void VpnController::logout()
{
    if (authenticationRecoveryRequired(m_authState)) {
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::logout));
}

void VpnController::disableKillSwitchForLogin()
{
    if (!m_backendAvailable || !m_ready || m_loggedIn || m_busy
        || m_killSwitch == 0 || authenticationRecoveryRequired(m_authState)) {
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
    const QVariant captureTarget = packetCaptureTargetActive(method);
    const QString connectionTarget = connectionTargetState(method);
    const bool riskReducingCaptureStop = captureTarget.isValid()
        && !captureTarget.toBool();
    if (!m_backendAvailable || m_backendDestination.isEmpty()
        || (!snapshotHealthy() && !riskReducingCaptureStop)) {
        return;
    }
    m_busy = true;
    m_message.clear();
    const quint64 foregroundGeneration = ++m_foregroundOperationGeneration;
    quint64 captureGeneration = 0;
    if (captureTarget.isValid()) {
        captureGeneration = ++m_packetCaptureOperationGeneration;
        m_packetCaptureOperationPending = true;
        m_packetCaptureExpectedActive = captureTarget.toBool();
        m_packetCaptureError.clear();
    }
    quint64 connectionGeneration = 0;
    if (!connectionTarget.isEmpty()) {
        connectionGeneration = ++m_connectionOperationGeneration;
        emit connectionOperationStarted(connectionGeneration, connectionTarget);
    }
    emit snapshotChanged();

    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    stampBackendRequest(watcher);
    watcher->setProperty("connectionTargetState", connectionTarget);
    watcher->setProperty(
        "foregroundOperationGeneration",
        QVariant::fromValue<qulonglong>(foregroundGeneration));
    watcher->setProperty("connectionOperationGeneration",
                         QVariant::fromValue<qulonglong>(connectionGeneration));
    watcher->setProperty("packetCaptureTargetActive", captureTarget);
    watcher->setProperty("restartAfterAccountRetirement",
                         method == QString::fromLatin1(BackendDbus::Method::logout));
    watcher->setProperty("packetCaptureOperationGeneration",
                         QVariant::fromValue<qulonglong>(captureGeneration));
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
                                        bool updateBusy,
                                        quint64 npsSubmissionGeneration,
                                        bool npsRetryAllowed)
{
    const bool npsSubmission = npsSubmissionGeneration != 0;
    if (!snapshotHealthy()) {
        if (npsSubmission) {
            finishNpsSurveySubmission(
                npsSubmissionGeneration,
                false,
                tr("The current account state is unavailable"),
                npsRetryAllowed);
        }
        return;
    }
    if (updateBusy) {
        m_busy = true;
        m_message.clear();
        emit snapshotChanged();
    }
    const quint64 foregroundGeneration = updateBusy
        ? ++m_foregroundOperationGeneration : 0;

    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        const QString failure = tr("The Proton backend is not available");
        if (updateBusy) {
            m_busy = false;
            m_message = failure;
            emit snapshotChanged();
        }
        if (npsSubmission) {
            finishNpsSurveySubmission(
                npsSubmissionGeneration, false, failure, npsRetryAllowed);
        }
        return;
    }
    const QString backendDestination = m_backendDestination;
    const quint64 backendGeneration = m_backendGeneration;
    const quint64 sessionGeneration = m_sessionGeneration;
    QDBusMessage keyRequest = QDBusMessage::createMethodCall(
        backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getAuthPublicKey));
    keyRequest << method;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(keyRequest, 5000), this);
    stampSessionRequest(watcher);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, method, fields, updateBusy, backendDestination,
             backendGeneration, sessionGeneration,
             npsSubmissionGeneration,
             npsRetryAllowed,
             foregroundGeneration](QDBusPendingCallWatcher *finished) {
        const bool npsSubmission = npsSubmissionGeneration != 0;
        const QDBusPendingReply<QString> reply = *finished;
        const bool current = sessionReplyIsCurrent(finished);
        finished->deleteLater();
        if (foregroundGeneration != 0
            && foregroundGeneration != m_foregroundOperationGeneration) {
            return;
        }
        if (!current
            || backendGeneration != m_backendGeneration
            || backendDestination != m_backendDestination
            || sessionGeneration != m_sessionGeneration) {
            if (npsSubmission) {
                finishNpsSurveySubmission(
                    npsSubmissionGeneration,
                    false,
                    tr("The Proton account session changed"),
                    false);
            }
            return;
        }
        if (reply.isError()) {
            const QString failure =
                tr("Unable to initialize protected authentication");
            if (updateBusy) {
                m_busy = false;
                m_message = failure;
                emit snapshotChanged();
            }
            if (npsSubmission) {
                finishNpsSurveySubmission(
                    npsSubmissionGeneration, false, failure,
                    npsRetryAllowed);
            }
            return;
        }

        QString errorMessage;
        const QByteArray publicKey = QByteArray::fromBase64(reply.value().toLatin1());
        const QDBusUnixFileDescriptor descriptor =
            SecretTransport::createSealedPayload(fields, publicKey, &errorMessage);
        if (!descriptor.isValid()) {
            const QString failure =
                tr("Unable to protect the authentication data: %1")
                    .arg(errorMessage);
            if (updateBusy) {
                m_busy = false;
                m_message = failure;
                emit snapshotChanged();
            }
            if (npsSubmission) {
                finishNpsSurveySubmission(
                    npsSubmissionGeneration, false, failure,
                    npsRetryAllowed);
            }
            return;
        }

        QDBusMessage request = QDBusMessage::createMethodCall(
            backendDestination, QString::fromLatin1(BackendDbus::objectPath),
            QString::fromLatin1(BackendDbus::interfaceName), method);
        request << QVariant::fromValue(descriptor);
        auto *operationWatcher = new QDBusPendingCallWatcher(
            QDBusConnection::sessionBus().asyncCall(request, 120000), this);
        stampSessionRequest(operationWatcher);
        operationWatcher->setProperty(
            "foregroundOperationGeneration",
            QVariant::fromValue<qulonglong>(foregroundGeneration));
        operationWatcher->setProperty(
            "npsSubmissionGeneration",
            QVariant::fromValue<qulonglong>(npsSubmissionGeneration));
        operationWatcher->setProperty("npsRetryAllowed", npsRetryAllowed);
        connect(operationWatcher, &QDBusPendingCallWatcher::finished, this,
                updateBusy ? &VpnController::handleOperationReply
                           : &VpnController::handleControlOperationReply);
    });
}

void VpnController::callControlOperation(const QString &method,
                                         const QVariantList &arguments)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()
        || !snapshotHealthy()) {
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
    const QString connectionTarget = connectionTargetState(method);
    const quint64 foregroundGeneration = connectionTarget.isEmpty()
        ? m_foregroundOperationGeneration : ++m_foregroundOperationGeneration;
    quint64 connectionGeneration = 0;
    if (!connectionTarget.isEmpty()) {
        connectionGeneration = ++m_connectionOperationGeneration;
        emit connectionOperationStarted(connectionGeneration, connectionTarget);
    }
    stampSessionRequest(watcher);
    watcher->setProperty("foregroundOwnershipRequired", true);
    watcher->setProperty(
        "foregroundOperationGeneration",
        QVariant::fromValue<qulonglong>(foregroundGeneration));
    watcher->setProperty("connectionTargetState", connectionTarget);
    watcher->setProperty("connectionOperationGeneration",
                         QVariant::fromValue<qulonglong>(connectionGeneration));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleControlOperationReply);
}
