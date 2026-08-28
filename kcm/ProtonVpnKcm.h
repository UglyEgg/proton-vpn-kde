#pragma once

#include "AppSettings.h"

#include <KQuickConfigModule>

class ProtonVpnKcm final : public KQuickConfigModule
{
    Q_OBJECT
    Q_PROPERTY(AppSettings *appSettings READ appSettings CONSTANT)

public:
    ProtonVpnKcm(QObject *parent, const KPluginMetaData &metadata);

    [[nodiscard]] AppSettings *appSettings() const;

    Q_INVOKABLE void openFullSettings();
    Q_INVOKABLE void openGlobalShortcuts();

private:
    AppSettings *m_settings = nullptr;
};
