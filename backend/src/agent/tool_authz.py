# tool_authz.py

ROLE_ADMIN = "ROLE_ADMIN"
ROLE_DISTRIBUTOR = "ROLE_DISTRIBUTOR"
ROLE_FUND = "ROLE_FUND"

TOOL_ROLE_MAP = {

    # ─── SLA Monitoring ───
    "getUnresolvedRecords": {ROLE_ADMIN},
    "getSlaBreachedRecords": {ROLE_ADMIN},
    "getAllSlaRecords": {ROLE_ADMIN},

    # ─── Order State History ───
    "getOrderStatesByOrderId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByFileId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByDistributorId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByFundhouseId": {ROLE_ADMIN, ROLE_FUND},
    "getAllOrderStates": {ROLE_ADMIN},

    # ─── Order Exceptions ───
    "getOrderExceptions": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderExceptionSummary": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrdersWithExceptions": {ROLE_ADMIN},

    # ─── Fundhouse Exceptions ───
    "getFundhouseStats": {ROLE_ADMIN, ROLE_FUND},
    "getFundhouseExceptions": {ROLE_ADMIN, ROLE_FUND},
    "getFundhouseExceptionById": {ROLE_ADMIN, ROLE_FUND},

    # ─── Firm Exceptions ───
    "getFirmStats": {ROLE_ADMIN},
    "getFirmExceptions": {ROLE_ADMIN},
    "getFirmExceptionById": {ROLE_ADMIN},

    # ─── Admin / NT Exceptions ───
    "getNtExceptions": {ROLE_ADMIN},
    "getNtExceptionById": {ROLE_ADMIN},
    "getNtExceptionStats": {ROLE_ADMIN},

    # ─── Exception Actions & Audits ───
    "takeAction": {ROLE_ADMIN},
    "getAuditsByTransaction": {ROLE_ADMIN},
    "getAuditsByFirm": {ROLE_ADMIN},

    # ─── Validation & Trades ───
    "validate": {ROLE_ADMIN},
    "getValidTrades": {ROLE_ADMIN},
    "getAllTrades": {ROLE_ADMIN},
    "getTradeById": {ROLE_ADMIN},
    "searchTradesByTransactionId": {ROLE_ADMIN},

    # ─── Clients ───
    "getAllClients": {ROLE_ADMIN},
    "getClientById": {ROLE_ADMIN},
    "searchClientsByPan": {ROLE_ADMIN},

    # ─── Funds ───
    "getAllFunds": {ROLE_ADMIN},
    "getFundById": {ROLE_ADMIN},

    # ─── Firms ───
    "getAllFirms": {ROLE_ADMIN},
    "getFirmById": {ROLE_ADMIN},

    # ─── Outbox & Events ───
    "getOutboxEvents": {ROLE_ADMIN},
    "getExceptionOutboxEntries": {ROLE_ADMIN},
    "getExceptionEvents": {ROLE_ADMIN},

    # ─── Dashboard ───
    "getDashboard": {ROLE_ADMIN},

    # ─── History / WebSocket ───
    "history": {ROLE_ADMIN},

    # ─── Admin Test / Debug ───
    "sendFirmException": {ROLE_ADMIN},
    "sendAdminException": {ROLE_ADMIN},
    "getRoutingInfo": {ROLE_ADMIN},
    "getAllOrderErrors": {ROLE_ADMIN},
    "s3Thread": {ROLE_ADMIN},
    "mqThread": {ROLE_ADMIN},

    # ─── Health / Infra ───
    "health": {ROLE_ADMIN},
    "healthCheck": {ROLE_ADMIN},

    "runNetting": {ROLE_ADMIN},


    # Distributor TC report
    "downloadTcReport": {ROLE_ADMIN, ROLE_DISTRIBUTOR},

    # Fund house netting report
    "downloadFundHouseReport": {ROLE_ADMIN, ROLE_FUND},


    # List of all generated netting reports
    "getAllReports": {ROLE_ADMIN},


    "health": {ROLE_ADMIN},

    # All fund houses netting
    "getFundHouseNetting": {ROLE_ADMIN, ROLE_FUND},

    # Specific fund house netting
    "getFundHouseNettingById": {ROLE_ADMIN, ROLE_FUND},

    # All distributors netting
    "getDistributorNetting": {ROLE_ADMIN, ROLE_DISTRIBUTOR},

    # Specific distributor netting
    "getDistributorNettingById": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "runFundHouseSettlement": {ROLE_ADMIN},
    "runDistributorSettlement": {ROLE_ADMIN},

    "getSettlementReceipts": {ROLE_ADMIN},

    "getFundingHouseNettingResults": {ROLE_ADMIN, ROLE_FUND},

    "getDistributorNettingResults": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "process": {ROLE_ADMIN},


    # Get all valuations (global visibility)
    "getAllValuations": {ROLE_ADMIN},

    # Paginated valuations (admin dashboards, ops)
    "getValuations": {ROLE_ADMIN},

    # Single distributor + fund position
    "getPosition": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUND},

    # All distributors under a fund
    "getFundPositions": {ROLE_ADMIN, ROLE_FUND},

    # All funds under a distributor
    "getDistributorPositions": {ROLE_ADMIN, ROLE_DISTRIBUTOR},

    # Global positions view
    "getAllPositions": {ROLE_ADMIN},
    # Validate canonical trade (stateless but sensitive)
    "validate": {ROLE_ADMIN},

    # Service health
    "health": {ROLE_ADMIN},


    "s3Thread": {ROLE_ADMIN},
    "mqThread": {ROLE_ADMIN},

    "getValidTrades": {ROLE_ADMIN},

    "getExceptionOutboxEntries": {ROLE_ADMIN},

    "getAllTrades": {ROLE_ADMIN},

    "getTradeById": {ROLE_ADMIN},

    "searchTradesByTransactionId": {ROLE_ADMIN},

    "searchClientsByPan": {ROLE_ADMIN},

    "getAllClients": {ROLE_ADMIN},

    "getClientById": {ROLE_ADMIN},

    "getAllFunds": {ROLE_ADMIN},

    "getFundById": {ROLE_ADMIN},

    "getAllFirms": {ROLE_ADMIN},

    "getFirmById": {ROLE_ADMIN},

    "getOutboxEvents": {ROLE_ADMIN},

    "getExceptionEvents": {ROLE_ADMIN},

    "getDashboard": {ROLE_ADMIN},
}
