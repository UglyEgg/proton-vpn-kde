#pragma once

#include <QObject>
#include <QString>

class VpnConnectionController : public QObject
{
    Q_OBJECT

public:
    using QObject::QObject;
    ~VpnConnectionController() override = default;

    [[nodiscard]] virtual bool backendAvailable() const = 0;
    [[nodiscard]] virtual bool ready() const = 0;
    [[nodiscard]] virtual bool loggedIn() const = 0;
    [[nodiscard]] virtual bool busy() const = 0;
    [[nodiscard]] virtual int killSwitch() const = 0;
    [[nodiscard]] virtual QString state() const = 0;
    [[nodiscard]] virtual QString serverName() const = 0;
    [[nodiscard]] virtual int forwardedPort() const = 0;
    [[nodiscard]] virtual QString message() const = 0;
    [[nodiscard]] virtual QString primaryActionText() const = 0;
    [[nodiscard]] virtual bool primaryActionEnabled() const = 0;

public slots:
    virtual void activatePrimaryAction() = 0;
    virtual void connectTarget(const QString &target) = 0;
    virtual void connectGroup(const QString &countryCode,
                              const QString &groupKind,
                              const QString &groupName) = 0;
    virtual void disconnect() = 0;

signals:
    void backendAvailableChanged();
    void snapshotChanged();
};
