
ROLE_ADMIN = "ROLE_ADMIN"
ROLE_DISTRIBUTOR = "ROLE_DISTRIBUTOR"
ROLE_FUNDHOUSE = "ROLE_FUND"

TOOL_ROLE_MAP = {

    "upload_reconciliation_files": {ROLE_ADMIN},
    "triggerRoutineReconciliation": {ROLE_ADMIN},

    "health": {ROLE_ADMIN},

    "getFundHouseReconciliations": {ROLE_ADMIN, ROLE_FUNDHOUSE},
    "getDistributorReconciliations": {ROLE_ADMIN, ROLE_DISTRIBUTOR},

    "getEntityReconciliations": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUNDHOUSE},
    "getSuccessfulReconciliations": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUNDHOUSE},
    "getFailedReconciliations": {ROLE_ADMIN, ROLE_DISTRIBUTOR, ROLE_FUNDHOUSE},

    "getAdhocReconciliationStatus": {ROLE_ADMIN},


    "getEligibleDates": {ROLE_ADMIN},

    "getAdminDashboard": {ROLE_ADMIN},
    "getAllReconciliations": {ROLE_ADMIN},
    "runFundHouseSettlement": {ROLE_ADMIN},
    "runDistributorSettlement": {ROLE_ADMIN},

    "getSettlementReceipts": {ROLE_ADMIN},

    "getFundingHouseNettingResults": {ROLE_ADMIN, ROLE_FUNDHOUSE},

    "getDistributorNettingResults": {ROLE_ADMIN, ROLE_DISTRIBUTOR},
}
