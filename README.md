# NN Fund Management Module

## Odoo Version
Odoo 17.0 Community Edition

## Description
A comprehensive fund management system for Odoo that handles:
- Incoming funds
- Fund allocations to projects and expense heads
- Fund requisitions
- Bill control against requisitions
- Fund transfers between projects/expense heads
- GM and MD approval workflows
- Balance tracking with double-spending prevention

---

## Installation Instructions

### Prerequisites
- Docker Desktop installed and running
- Git installed

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/fardina-tahsin/Fund-management.git
cd nn_fund_management_project
```

**2. Initialize the database and install the module**
```bash
docker compose run --rm odoo odoo \
  --db_host=db \
  --db_user=odoo \
  --db_password=odoo \
  -d odoo \
  -i base,nn_fund_management \
  --stop-after-init
```

**3. Start Odoo**
```bash
docker compose up -d
```

**4. Open browser**

`http://localhost:8069`

**5. Login**
- Email: `admin`
- Password: `admin`

---

## Required Dependencies

### Odoo Modules
- `base`
- `mail`

### System Requirements
- Docker Desktop
- PostgreSQL 15 (via Docker)
- Python 3.11+ (via Docker)

---

## Configuration Steps

**1. Set company currency to BDT**
- Settings → Companies → Your Company → Currency → BDT

**2. Assign security groups to users**
- Settings → Users & Companies → Users
- Available groups:
  - Fund User - basic access
  - Finance User - confirm incoming funds
  - GM Approver - first level approvals
  - MD Approver - second level approvals
  - Fund Administrator - full access

**3. Create Fund Accounts**
- Fund Management → Fund Accounts → New

**4. Create Projects and Expense Heads**
- Fund Management → Configuration → Projects
- Fund Management → Configuration → Expense Heads

---

## Testing Instructions

### Full Demo Flow

**Create Fund Account**
- Fund Management → Fund Accounts → New
- Name: `Main Fund`, Code: `MF001`, Type: `Bank`
- Save

**Create Projects**
- Fund Management → Configuration → Projects → New
- Name: `Project A`, Code: `PA001` → Save
- New → Name: `Project B`, Code: `PB001` → Save

**Step 1 - Receive BDT 1,000,000**
- Fund Management → Incoming Funds → New
- Fund Account: `Main Fund`
- Amount: `1,000,000`
- Transaction Reference: `TXN001`
- Click **Confirm**

Expected: 
Fund Account → 
Total Received = 1,000,000 | Unassigned Balance = 1,000,000

**Step 2 - Request BDT 600,000 for Project A**
- Fund Management → Fund Allocations → New
- Fund Account: `Main Fund`
- Project: `Project A`
- Amount: `600,000`
- Purpose: `Initial allocation for Project A`
- Click **Submit**

Expected:
Fund Account → 
On Hold = 600,000 | Unassigned = 400,000

The 600,000 is frozen and cannot be used by another request

**Step 3 - Reject and verify money returns**
- On the same allocation click **Reject**
- Go to Fund Account → Main Fund

Expected: 
Unassigned Balance = 1,000,000 | On Hold = 0

Money fully returned to unassigned balance

**Step 4 - Resubmit and fully approve**
- Go back to the allocation
- Click **Reset to Draft**
- Click **Submit**
- Click **GM Approve**
- Click **MD Approve**

Expected: 
Fund Account → 
Assigned = 600,000 | Unassigned = 400,000

Expected: 
Project A → Available Balance = 600,000

**Step 5 - Transfer BDT 200,000 from Project A to Project B**
- Fund Management → Fund Transfers → New
- Source Project: `Project A`
- Destination Project: `Project B`
- Amount: `200,000`
- Reason: `Transferring funds to Project B`
- Click **Submit**

Expected: 
Project A → 
Transfer Hold = 200,000 | Available = 400,000

The 200,000 is frozen and cannot be spent or requisitioned

**Step 6 — Approve the transfer**
- Click **GM Approve**
- Click **MD Approve**

Expected: 
Project A → 
Available Balance = 400,000

Expected: 
Project B → 
Available Balance = 200,000

Money successfully moved between projects

**Step 7 - Create BDT 150,000 requisition for Project B**
- Fund Management → Fund Requisitions → New
- Project: `Project B`
- Amount: `150,000`
- Purpose: `Project B operational expenses`
- Click **Submit**

Expected: 
Project B → 
Requisition Hold = 150,000 | Available = 50,000

- Click **GM Approve**
- Click **MD Approve**

Expected: 
Amount reserved for bills against this requisition

**Step 8 - Create BDT 100,000 partial bill**
- Fund Management → Fund Bills → New
- Requisition: select the approved requisition
- Amount: `100,000`
- Vendor: `Test Vendor`
- Click **Post**

Expected:
Requisition → 
Billed Amount = 100,000 | Remaining Billable = 50,000

Expected: 
Project B → 
Total Spent increases by 100,000

**Step 9 - Try BDT 60,000 bill (must be blocked)**
- Fund Management → Fund Bills → New
- Same requisition as above
- Amount: `60,000`
- Click **Post**

Expected: 
System blocks with error:
> "Bill amount exceeds remaining billable amount"

**Step 10 - Verify cross-project billing is structurally blocked**
- Fund Management → Fund Bills → New
- Select the **Project B requisition**
- Notice the **Project** field is read-only and automatically set to Project B
- There is no way to change it to Project A

Expected: 
Project field is locked to the requisition's project

**Step 11 - Verify Audit Log**
- Fund Management → Audit Log

Expected: 
All actions recorded - submissions, approvals, rejections with user, date, amount and status changes

---

### Key Business Rules to Test
- Cannot allocate more than unassigned balance
- Cannot requisition more than project available balance
- Cannot bill more than requisition remaining amount
- Cannot transfer to same source and destination
- GM must approve before MD
- Duplicate transaction references blocked per account

---

## Assumptions
- One company per deployment
- BDT is the primary currency
- Admin user has full access by default
- Approval is sequential: GM always before MD
- A transaction uses either a project OR expense head, never both
- Multiple partial bills are allowed against one requisition
- Balances are computed on demand (not stored) for accuracy

---

## Known Limitations
- Balance fields recompute on demand, not real-time triggers
- No email notifications for approvals yet
- No dashboard implemented yet
- Bank email integration not implemented
- Configurable approval tiers not implemented
- No automated tests yet


