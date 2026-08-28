#pragma once

#include <QObject>
#include <QString>

class QAction;
class QWindow;
class VpnController;

class ShortcutIntegration final : public QObject
{
    Q_OBJECT

public:
    ShortcutIntegration(VpnController *controller, QWindow *window,
                        QObject *parent = nullptr);

private:
    QAction *registerAction(const QString &id, const QString &text);
    void toggleWindow();

    VpnController *m_controller = nullptr;
    QWindow *m_window = nullptr;
};
