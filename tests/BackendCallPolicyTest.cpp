#include "BackendCallPolicy.h"
#include "ClientRegistrationState.h"

#include <QTest>

using ProtonVpnKde::BackendCallFailure;
using ProtonVpnKde::ClientRegistrationState;

class BackendCallPolicyTest final : public QObject
{
    Q_OBJECT

private slots:
    void classifiesBackendFailures();
    void registersOnlyAfterSuccessfulReply();
    void ignoresRepliesFromAnOldServiceGeneration();
};

void BackendCallPolicyTest::classifiesBackendFailures()
{
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
            QDBusError::Other, u"quest.entropy.PlasmaVPN.Error.OperationFailed"),
        BackendCallFailure::Rejected);
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
