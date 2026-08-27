#pragma once

#include <QObject>

class QAction;
class QMenu;
class QWindow;
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
    TrayIntegration(VpnController *controller, QWindow *window,
                    QObject *parent = nullptr);

private:
    void toggleWindow();
    void updateState();

    VpnController *m_controller = nullptr;
    QWindow *m_window = nullptr;
    QMenu *m_menu = nullptr;
    QAction *m_showAction = nullptr;
    QAction *m_connectionAction = nullptr;

#ifdef HAVE_KSTATUSNOTIFIERITEM
    KStatusNotifierItem *m_tray = nullptr;
#else
    QSystemTrayIcon *m_tray = nullptr;
#endif
};
