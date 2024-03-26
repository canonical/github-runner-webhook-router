<!-- markdownlint-disable -->

<a href="../src/validation.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `validation.py`
Module for validating the webhook request. 


---

<a href="../src/validation.py#L10"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `verify_signature`

```python
verify_signature(
    payload: bytes,
    secret_token: str,
    signature_header: str
) → bool
```

Verify that the payload was sent from GitHub by validating SHA256. 

Raise error if the signature doesn't match. 



**Args:**
 
 - <b>`payload`</b>:  original request body to verify 
 - <b>`secret_token`</b>:  GitHub app webhook token (WEBHOOK_SECRET) 
 - <b>`signature_header`</b>:  header received from GitHub (x-hub-signature-256) 



**Returns:**
 True if the signature is valid, False otherwise. 


