<!-- markdownlint-disable -->

<a href="../webhook_router/app.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `app.py`
Flask application which receives GitHub webhooks and logs those. 

**Global Variables**
---------------
- **SUPPORTED_GITHUB_EVENT**
- **GITHUB_EVENT_HEADER**
- **WEBHOOK_SIGNATURE_HEADER**

---

<a href="../webhook_router/app.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `handle_github_webhook`

```python
handle_github_webhook() → tuple[str, int]
```

Receive a GitHub webhook and append the payload to a file. 



**Returns:**
  A tuple containing an empty string and 200 status code on success or  a failure message and 403 status code. 


---

<a href="../webhook_router/app.py#L78"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `health_check`

```python
health_check() → tuple[str, int]
```

Health check endpoint. 



**Returns:**
  A tuple containing an empty string and 200 status code. 


