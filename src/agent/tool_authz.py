# tool_authz.py (recommended)

ROLE_ADMIN = "admin"
ROLE_DISTRIBUTOR = "distributor"
ROLE_FUNDHOUSE = "fundhouse"

TOOL_ROLE_MAP = {
    # ─── SLA Monitoring ───
    "getUnresolvedRecords": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUNDHOUSE},
    "getSlaBreachedRecords": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getAllSlaRecords": {ROLE_ADMIN},

    # ─── Order State History ───
    "getOrderStatesByOrderId": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUNDHOUSE},
    "getOrderStatesByFileId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByDistributorId": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderStatesByFundhouseId": {ROLE_ADMIN, ROLE_FUNDHOUSE},
    "getAllOrderStates": {ROLE_ADMIN},

    # ─── Exceptions ───
    "getOrderExceptions": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "getOrderExceptionSummary": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
    "takeAction": {ROLE_ADMIN},

    # ─── Admin APIs ───
    "getDashboard": {ROLE_ADMIN},
    "getAllTrades": {ROLE_ADMIN},
    "getTradeById": {ROLE_ADMIN},
    "searchTradesByTransactionId": {ROLE_ADMIN},
    "getAllFunds": {ROLE_ADMIN},
    "getAllClients": {ROLE_ADMIN},
    "getAllFirms": {ROLE_ADMIN},

    # ─── Infra ───
    "health": {ROLE_ADMIN},
    "healthCheck": {ROLE_ADMIN},
}
