#pragma once

#include <QObject>
#include <functional>
#include <QString>

class QAction;
class VpnConnectionController;

class ShortcutIntegration final : public QObject
{
    Q_OBJECT

public:
    ShortcutIntegration(VpnConnectionController *controller,
                        std::function<void()> showControlCenter,
                        QObject *parent = nullptr);

private:
    QAction *registerAction(const QString &id, const QString &text);
    void showControlCenter();

    VpnConnectionController *m_controller = nullptr;
    std::function<void()> m_showControlCenter;
};
