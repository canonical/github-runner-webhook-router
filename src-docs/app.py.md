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

<a href="../webhook_router/app.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `config_app`

```python
config_app(flask_app: Flask) → None
```

Configure the application. 



**Args:**
 
 - <b>`flask_app`</b>:  The Flask application to configure. 


---

<a href="../webhook_router/app.py#L93"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `health_check`

```python
health_check() → tuple[str, int]
```

Health check endpoint. 



**Returns:**
  A tuple containing an empty string and 200 status code. 


---

<a href="../webhook_router/app.py#L103"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `handle_github_webhook`

```python
handle_github_webhook() → tuple[str, int]
```

Receive a GitHub webhook and append the payload to a file. 



**Returns:**
  A tuple containing an empty string and 200 status code on success or  a failure message and 4xx status code. 


---

## <kbd>class</kbd> `ConfigError`
Raised when a configuration error occurs. 





---

## <kbd>class</kbd> `ValidationResult`
ValidationResult(is_valid, msg) 





