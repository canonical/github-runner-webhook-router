<!-- markdownlint-disable -->

<a href="../src/app.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `app.py`
Flask application which receives GitHub webhooks and logs those. 

**Global Variables**
---------------
- **WEBHOOK_SIGNATURE_HEADER**
- **webhook_secret**

---

<a href="../src/app.py#L30"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_logger`

```python
setup_logger(log_file: Path) → None
```

Set up the webhook logger to log to a file. 



**Args:**
 
 - <b>`log_file`</b>:  The log file. 


---

<a href="../src/app.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `signature_validator`

```python
signature_validator(
    func: Callable[[], tuple[str, int]]
) → Callable[[], tuple[str, int]]
```

Validate the signature of the incoming request. 



**Args:**
 
 - <b>`func`</b>:  function to be decorated. 



**Returns:**
 Decorated function. 


---

<a href="../src/app.py#L91"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `handle_github_webhook`

```python
handle_github_webhook() → tuple[str, int]
```

Receive a GitHub webhook and append the payload to a file. 



**Returns:**
  A tuple containing an empty string and 200 status code. 


