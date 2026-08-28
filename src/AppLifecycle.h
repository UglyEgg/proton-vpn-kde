#pragma once

#include <QObject>
#include <QString>

class AppLifecycle final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool quitPending READ quitPending NOTIFY quitPendingChanged)

public:
    explicit AppLifecycle(QObject *parent = nullptr);

    [[nodiscard]] bool quitPending() const;

    Q_INVOKABLE void requestQuit(const QString &connectionState,
                                 bool canDisconnect);
    void observeConnectionState(const QString &connectionState);

    Q_INVOKABLE void confirmQuit();
    Q_INVOKABLE void cancelQuit();

signals:
    void quitConfirmationRequested();
    void disconnectRequested();
    void quitReady();
    void quitPendingChanged();

private:
    enum class QuitState {
        Idle,
        AwaitingConfirmation,
        Disconnecting,
    };

    void setQuitState(QuitState state);

    QuitState m_quitState = QuitState::Idle;
    QString m_connectionState = QStringLiteral("unavailable");
    bool m_canDisconnect = false;
};
