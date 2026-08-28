#pragma once

#include <QList>
#include <QObject>

class QAction;
class QMenu;
class QWindow;
class AppSettings;
class VpnController;

#ifdef HAVE_KSTATUSNOTIFIERITEM
class KStatusNotifierItem;
#else
class QSystemTrayIcon;
#endif

class TrayIntegration final : public QObject
{
    Q_OBJECT

public:
    TrayIntegration(VpnController *controller, AppSettings *settings, QWindow *window,
                    QObject *parent = nullptr);

private:
    void toggleWindow();
    void updateState();
    void rebuildPinnedActions();

    VpnController *m_controller = nullptr;
    AppSettings *m_settings = nullptr;
    QWindow *m_window = nullptr;
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
