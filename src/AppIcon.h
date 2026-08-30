#pragma once

#include <QIcon>
#include <QString>

namespace ProtonVpnKde
{
[[nodiscard]] QIcon applicationIcon();
[[nodiscard]] QIcon applicationIcon(const QString &style);
[[nodiscard]] QString applicationIconSource(const QString &style);
}
