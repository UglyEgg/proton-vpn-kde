#pragma once

#include <QList>
#include <QObject>
#include <functional>

class QAction;
class QMenu;
class AppSettings;
class VpnConnectionController;

#ifdef HAVE_KSTATUSNOTIFIERITEM
class KStatusNotifierItem;
#else
class QSystemTrayIcon;
#endif

class TrayIntegration final : public QObject
{
    Q_OBJECT

public:
    TrayIntegration(VpnConnectionController *controller, AppSettings *settings,
                    std::function<void()> showControlCenter,
                    QObject *parent = nullptr);

private:
    void showControlCenter();
    void updateState();
    void rebuildPinnedActions();

    VpnConnectionController *m_controller = nullptr;
    AppSettings *m_settings = nullptr;
    std::function<void()> m_showControlCenter;
    QMenu *m_menu = nullptr;
    QAction *m_showAction = nullptr;
    QAction *m_connectionAction = nullptr;
    QAction *m_pinnedSeparator = nullptr;
    QList<QAction *> m_pinnedActions;

#ifdef HAVE_KSTATUSNOTIFIERITEM
    KStatusNotifierItem *m_tray = nullptr;
#else
    QSystemTrayIcon *m_tray = nullptr;
#endif
};
