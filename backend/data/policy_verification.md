# NovaShip verification policy (knowledge base for Ask AI)

## Source of truth
The Shipping Instruction (SI) is always the source of truth. The Draft Bill of Lading (BL) must reflect the SI. When they differ, the BL is corrected, never the SI.

## The seven required fields
Exactly seven fields are compared on every case: Shipper, Consignee, Notify Party, Port of Loading, Port of Discharge, Container Count, Gross Weight in kilograms. Every field is compared independently. A mismatch in one field never marks another field as wrong. When all seven match the canonical result is the exact phrase "No mismatch detected."

## Safe normalization
Only formatting differences are normalized: letter case, repeated spaces, punctuation spacing, weight units ("22,000 KG" equals "22000 kg" equals "22 000 kilograms"), container counts written as "3 x 40'HC" equal 3, and a trailing UN/LOCODE such as (MYPKG) on a port name. Legal names are never rewritten: "MOORIM SP CO., LTD" and "MOORIM SP CO LTD" are treated as different parties until a supervisor confirms.

## Human review
Any field with extraction confidence below 0.85, any blank value (???, TBA, N/A, underscores), any unreadable scan, and any wrong document type (invoice or packing list instead of a Draft BL) routes the case to HUMAN_REVIEW. No mismatch is asserted in those cases.

## Communication
External email is never auto-sent. Every external draft requires human approval by a Supervisor or Admin. Operations staff may share internally. The Notify Party extracted from the documents is a comparison value only and is not authorisation to contact that party; an approved party contact must be selected and confirmed.
