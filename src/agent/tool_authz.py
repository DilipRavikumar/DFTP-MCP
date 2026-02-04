# tool_authz.py

ROLE_ADMIN = "admin"
ROLE_DISTRIBUTOR = "distributor"
ROLE_FUNDHOUSE = "fundhouse"

TOOL_ROLE_MAP = {

    # ─── SLA Monitoring ───
    "getUnresolvedRecords": {ROLE_ADMIN},
    "getSlaBreachedRecords": {ROLE_ADMIN},
    "getAllSlaRecords": {ROLE_ADMIN},

    # ─── Order State History ───
    "getOrderStatesByOrderId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByFileId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByDistributorId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByFundhouseId": {ROLE_ADMIN, ROLE_FUNDHOUSE},
    "getAllOrderStates": {ROLE_ADMIN},

    # ─── Order Exceptions ───
    "getOrderExceptions": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderExceptionSummary": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrdersWithExceptions": {ROLE_ADMIN},

    # ─── Fundhouse Exceptions ───
    "getFundhouseStats": {ROLE_ADMIN, ROLE_FUNDHOUSE},
    "getFundhouseExceptions": {ROLE_ADMIN, ROLE_FUNDHOUSE},
    "getFundhouseExceptionById": {ROLE_ADMIN, ROLE_FUNDHOUSE},

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
}
