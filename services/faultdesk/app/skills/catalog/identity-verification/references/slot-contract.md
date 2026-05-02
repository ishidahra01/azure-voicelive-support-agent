# Identity Slot Contract

The `verify_identity` backend tool updates these `identity` slots when possible:

- `customer_id`: 8 digit customer identifier.
- `name_match`: true when the caller's name matches the customer record.
- `address_match`: true when the caller's address or customer ID verifies the record.
- `contact_phone`: contact phone from SF113.
- `verification_status`: `verified` or a failure reason such as `customer_id_not_found`.