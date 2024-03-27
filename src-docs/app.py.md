<!-- markdownlint-disable -->

<a href="../webhook_router/app.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `app.py`
Flask application which receives GitHub webhooks and logs those. 

**Global Variables**
---------------
- **WEBHOOK_SIGNATURE_HEADER**
- **webhook_secret**

---

<a href="../webhook_router/app.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `handle_github_webhook`

```python
handle_github_webhook() → tuple[str, int]
```

Receive a GitHub webhook and append the payload to a file. 



**Returns:**
  A tuple containing an empty string and 200 status code. 


