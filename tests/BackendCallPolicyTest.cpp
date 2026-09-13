// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackendCallPolicy.h"
#include "ClientRegistrationState.h"
#include "OperationCompletion.h"

#include <QTest>

using ProtonVpnKde::BackendCallFailure;
using ProtonVpnKde::ClientRegistrationState;

class BackendCallPolicyTest final : public QObject
{
    Q_OBJECT

private slots:
    void classifiesBackendFailures();
    void reconciliationRetainsItsGenerationUntilTerminal();
    void registersOnlyAfterSuccessfulReply();
    void ignoresRepliesFromAnOldServiceGeneration();
};

void BackendCallPolicyTest::reconciliationRetainsItsGenerationUntilTerminal()
{
    ProtonVpnKde::OperationCompletion completion;
    const auto first = completion.begin();
    QVERIFY(!completion.settleIfIdle(first, true)); // Signal before method reply.
    completion.reconcile(first);
    QVERIFY(!completion.settleIfIdle(first, false)); // Still busy.
    QVERIFY(completion.settleIfIdle(first, true));
    QVERIFY(!completion.settleIfIdle(first, true)); // Exactly one release.
    const auto second = completion.begin();
    completion.reconcile(first);
    QVERIFY(!completion.settleIfIdle(second, true));
    completion.reconcile(second);
    QVERIFY(!completion.settleIfIdle(first, true));
    completion.invalidate();
    QVERIFY(!completion.settleIfIdle(second, true));
}

void BackendCallPolicyTest::classifiesBackendFailures()
{
    for (const auto type : {QDBusError::Timeout, QDBusError::NoReply,
                            QDBusError::NoNetwork}) {
        QCOMPARE(ProtonVpnKde::classifyBackendCallFailure(type, QStringView()),
                 BackendCallFailure::CompletionUnknown);
    }
    QVERIFY(ProtonVpnKde::isTransientSameOwnerFailure(QDBusError::Timeout));
    QVERIFY(ProtonVpnKde::isTransientSameOwnerFailure(QDBusError::NoReply));
    QVERIFY(!ProtonVpnKde::isTransientSameOwnerFailure(
        QDBusError::ServiceUnknown));
    QCOMPARE(
        ProtonVpnKde::classifyBackendCallFailure(
            QDBusError::ServiceUnknown, QStringView()),
        BackendCallFailure::Unavailable);
    QCOMPARE(
        ProtonVpnKde::classifyBackendCallFailure(
            QDBusError::Other,
            u"quest.entropy.PlasmaVPN.Error.InvalidSecretPayload"),
        BackendCallFailure::InvalidSecretPayload);
    QCOMPARE(
        ProtonVpnKde::classifyBackendCallFailure(
            QDBusError::Other,
            u"quest.entropy.PlasmaVPN.Error.Unauthorized"),
        BackendCallFailure::Unauthorized);
    QCOMPARE(
        ProtonVpnKde::classifyBackendCallFailure(
            QDBusError::Other, u"quest.entropy.PlasmaVPN.Error.OperationFailed"),
        BackendCallFailure::Rejected);
    QVERIFY(ProtonVpnKde::isSafeBackendAuthoredMessage(
        u"quest.entropy.PlasmaVPN.Error.OperationFailed",
        u"Sign-out failed and the Proton session could not be restored"));
    QVERIFY(!ProtonVpnKde::isSafeBackendAuthoredMessage(
        u"org.freedesktop.DBus.Error.Failed", u"private implementation detail"));
    QVERIFY(!ProtonVpnKde::isSafeBackendAuthoredMessage(
        u"quest.entropy.PlasmaVPN.Error.OperationFailed", u"line one\nline two"));
}

void BackendCallPolicyTest::registersOnlyAfterSuccessfulReply()
{
    ClientRegistrationState state;

    const auto first = state.begin();
    QVERIFY(first.has_value());
    QVERIFY(state.inFlight());
    QVERIFY(!state.registered());
    QVERIFY(!state.begin().has_value());

    QCOMPARE(
        state.complete(*first, false),
        ClientRegistrationState::Completion::Failed);
    QVERIFY(!state.inFlight());
    QVERIFY(!state.registered());

    const auto retry = state.begin();
    QVERIFY(retry.has_value());
    QCOMPARE(
        state.complete(*retry, true),
        ClientRegistrationState::Completion::Registered);
    QVERIFY(state.registered());
    QVERIFY(!state.begin().has_value());
}

void BackendCallPolicyTest::ignoresRepliesFromAnOldServiceGeneration()
{
    ClientRegistrationState state;
    const auto oldRequest = state.begin();
    QVERIFY(oldRequest.has_value());

    state.serviceChanged();
    const auto currentRequest = state.begin();
    QVERIFY(currentRequest.has_value());

    QCOMPARE(
        state.complete(*oldRequest, true),
        ClientRegistrationState::Completion::Stale);
    QVERIFY(state.inFlight());
    QVERIFY(!state.registered());

    QCOMPARE(
        state.complete(*currentRequest, true),
        ClientRegistrationState::Completion::Registered);
    QVERIFY(state.registered());
}

QTEST_GUILESS_MAIN(BackendCallPolicyTest)

#include "BackendCallPolicyTest.moc"
