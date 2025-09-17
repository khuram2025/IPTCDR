# 3CX Quota & External Call Control Features

## Features Implemented

### 1. Quota Usage UI with Dynamic External Call Control
- **Purpose:** Allow admins to view quotas per extension and dynamically block/allow external calls for any extension.
- **Key Files:**
  - `cdr/templates/cdr/quota/quota_usage.html`: UI for quota usage, actions column with dynamic button.
  - `cdr/cdr3cx/quota_views.py`: Backend logic for quota usage and AJAX endpoint for toggling external calls.
  - `cdr/cdr3cx/blockExternalCall.py`: Handles PBX API calls to enable/disable external calls for extensions.
  - `cdr/cdr3cx/urls.py`: Registers the AJAX endpoint for toggling external calls.

### 2. Extension Model Update
- **Purpose:** Store and reflect whether external calls are currently allowed or blocked for each extension.
- **Key Files:**
  - `cdr/accounts/models.py`: Added `disable_external_call` BooleanField to the Extension model.

### 3. Integration with PBX API
- **Purpose:** Ensure UI actions actually enable/disable external calls on the PBX system.
- **Key Files:**
  - `cdr/cdr3cx/blockExternalCall.py`: Contains `set_external_call()` for PBX PATCH requests. All print statements disabled for production cleanliness.

### 4. Error Handling & User Feedback
- **Purpose:** Show accurate success/failure feedback in the UI, including proper handling of PBX 204 No Content responses.
- **Key Files:**
  - `cdr/templates/cdr/quota/quota_usage.html`: JavaScript for AJAX and UI updates.
  - `cdr/cdr3cx/blockExternalCall.py`: Improved HTTP status handling.

## How It Works
- Admin can block/allow external calls for any extension from the quota usage page.
- The button reflects the current state ("Block External Calls" or "Allow External Calls").
- Clicking the button updates the PBX and the Django model, and updates the UI without a page reload.

---

### 5. Planned: Auto-Blocking Extensions Based on Quota/Billing
- **Purpose:** Automatically block external calls for extensions that exceed their quota or run out of balance.
- **How:** After each billing/quota update, check if the extension should be blocked and trigger the PBX API call. Update the model to reflect the new state.
- **Key Files:**  
  - `cdr/cdr3cx/blockExternalCall.py` (PBX API logic)  
  - `cdr/cdr3cx/quota_views.py` or billing logic location (where to add the check)
- **Example Logic:**

```python
from cdr3cx.blockExternalCall import set_external_call

def check_and_block_if_needed(user_quota):
    if user_quota.remaining_balance <= 0 and not user_quota.extension.disable_external_call:
        set_external_call(user_quota.extension.extension, allow_external=False)
        user_quota.extension.disable_external_call = True
        user_quota.extension.save()
```
- Call this logic after every quota/balance update or periodically via a scheduled task.

**For further details, see code comments in the respective files.**
