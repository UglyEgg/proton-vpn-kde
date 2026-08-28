#include "AppLifecycle.h"

AppLifecycle::AppLifecycle(QObject *parent)
    : QObject(parent)
{
}

bool AppLifecycle::quitPending() const
{
    return m_quitState == QuitState::Disconnecting;
}

void AppLifecycle::requestQuit(const QString &connectionState, bool canDisconnect)
{
    m_connectionState = connectionState;
    m_canDisconnect = canDisconnect;
    if (m_quitState != QuitState::Idle) {
        return;
    }
    if (m_connectionState == QStringLiteral("disconnected") || !m_canDisconnect) {
        emit quitReady();
        return;
    }
    setQuitState(QuitState::AwaitingConfirmation);
    emit quitConfirmationRequested();
}

void AppLifecycle::observeConnectionState(const QString &connectionState)
{
    m_connectionState = connectionState;
    if (m_quitState == QuitState::Disconnecting
        && m_connectionState == QStringLiteral("disconnected")) {
        setQuitState(QuitState::Idle);
        emit quitReady();
    }
}

void AppLifecycle::confirmQuit()
{
    if (m_quitState != QuitState::AwaitingConfirmation) {
        return;
    }
    if (m_connectionState == QStringLiteral("disconnected") || !m_canDisconnect) {
        setQuitState(QuitState::Idle);
        emit quitReady();
        return;
    }
    setQuitState(QuitState::Disconnecting);
    emit disconnectRequested();
}

void AppLifecycle::cancelQuit()
{
    if (m_quitState == QuitState::AwaitingConfirmation) {
        setQuitState(QuitState::Idle);
    }
}

void AppLifecycle::setQuitState(QuitState state)
{
    const bool wasPending = quitPending();
    m_quitState = state;
    if (wasPending != quitPending()) {
        emit quitPendingChanged();
    }
}
