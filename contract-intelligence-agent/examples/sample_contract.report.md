# Contract Analysis — sample_contract.pdf

**Overall risk:** 🟠 High  
**Pages analyzed:** 3  
**Model:** `claude-opus-4-8`  
**Analyzed at:** 2026-06-20 18:00 UTC

## Executive Summary

This Master Services Agreement is materially vendor-favorable. The client bears unlimited, uncapped indemnification while the provider may terminate for convenience on 30 days' notice; broad IP assignment, 12-month auto-renewal, and a jury-trial/class-action waiver in a distant arbitration venue compound the exposure. Recommend negotiating a liability cap, mutual termination rights, and a more neutral venue before signing.

## Risk Register

_5 risk(s) identified: 1 critical, 2 high, 2 medium._

### 1. 🔴 Critical — Uncapped client indemnification
*Category: Liability*

Section 5.2 makes the client's indemnity explicitly unlimited and carves it out of the mutual limitation-of-liability cap, exposing the client to potentially unbounded liability for third-party claims.

**Recommendation:** Cap total indemnity at fees paid in the trailing 12 months and make the carve-out mutual; require Provider indemnity for IP infringement.

> shall be unlimited and shall not be subject to any cap on liability

### 2. 🟠 High — Asymmetric termination rights
*Category: Termination*

Provider can terminate for convenience on 30 days' notice while the client can only terminate for uncured material breach, leaving the client without an exit and exposed to mid-project abandonment.

**Recommendation:** Add a reciprocal termination-for-convenience right for the client, and a transition-assistance/wind-down obligation on Provider.

> Provider may terminate this Agreement at any time, for any reason or no reason

### 3. 🟠 High — Distant mandatory venue and jury/class waiver
*Category: Dispute Resolution*

Mandatory arbitration in Clark County, Nevada under Nevada law, plus a jury-trial and class-action waiver, raises the cost and friction of enforcing the client's rights if the client is not Nevada-based.

**Recommendation:** Negotiate a neutral or client-favorable venue, or at minimum allow remote arbitration; reconsider the class-action waiver.

> binding arbitration administered in Clark County, Nevada

### 4. 🟡 Medium — Auto-renewal with long notice window
*Category: Termination*

The agreement auto-renews for 12-month terms unless 90 days' written notice is given, which can trap the client into an unwanted renewal if the deadline is missed.

**Recommendation:** Add a calendar reminder for the notice deadline, shorten the renewal term to month-to-month after the initial term, or reduce the notice period to 30 days.

> automatically renew for successive twelve (12) month periods

### 5. 🟡 Medium — Short payment window with non-refundable fees
*Category: Payment Terms*

Net-15 payment combined with non-refundable fees and a 10-day suspension trigger gives the client little tolerance and no recourse for prepaid amounts.

**Recommendation:** Negotiate net-30, a cure period before suspension, and pro-rata refunds for terminated-but-prepaid services.

> due and payable within fifteen (15) days

## Key Clauses

### Payment Terms

- **Net-15 payment, non-refundable** _(p. 1)_: Provider invoices monthly in arrears; invoices are due within 15 days, and all fees are non-refundable.
  > All invoices are due and payable within fifteen (15) days of the invoice date. ... All fees are non-refundable.
- **Late interest and suspension** _(p. 1)_: Overdue amounts accrue 1.5%/month and Provider may suspend services after 10 days past due.
  > any amount not paid when due shall accrue interest at the rate of one and one-half percent (1.5%) per month ... Provider may suspend services if any undisputed invoice remains unpaid for more than ten (10) days

### Termination

- **Auto-renewal with 90-day notice** _(p. 2)_: 12-month term auto-renews for successive 12-month periods unless either party gives 90 days' written notice.
  > shall automatically renew for successive twelve (12) month periods unless either party provides written notice of non-renewal at least ninety (90) days prior
- **Unilateral termination for convenience** _(p. 2)_: Provider may terminate at any time on 30 days' notice; Client may terminate only for uncured material breach after 60 days.
  > Provider may terminate this Agreement at any time, for any reason or no reason, upon thirty (30) days' written notice ... Client may terminate only for Provider's material breach that remains uncured for sixty (60) days

### Ip Ownership

- **Assignment of work product to Client** _(p. 2)_: All work product and IP developed under the Agreement is assigned to Client; Provider keeps pre-existing tools and grants a license.
  > Provider hereby irrevocably assigns to Client all right, title, and interest therein. ... grants Client a non-exclusive license to use them solely as embedded in the deliverables.

### Liability

- **Consequential-damages waiver with carve-outs** _(p. 2)_: Mutual waiver of indirect/consequential damages, except indemnity and confidentiality breaches.
  > IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
- **Uncapped Client indemnification** _(p. 2)_: Client's indemnification is explicitly unlimited and not subject to any liability cap.
  > Client's indemnification obligations under Section 5.3 shall be unlimited and shall not be subject to any cap on liability.

### Dispute Resolution

- **Nevada law, Clark County arbitration, jury waiver** _(p. 3)_: Governed by Nevada law; disputes resolved by binding arbitration in Clark County; jury trial and class actions waived.
  > resolved exclusively by binding arbitration administered in Clark County, Nevada. ... EACH PARTY WAIVES ANY RIGHT TO A TRIAL BY JURY AND TO PARTICIPATE IN A CLASS ACTION.

---
_Generated by the Lumifie Consulting Contract Intelligence Agent. Token usage: 18,432 in / 2,987 out. This report is informational and is not legal advice._
