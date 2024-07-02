<!-- markdownlint-disable -->

<a href="../webhook_router/webhook/parse.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `parse`
Module for parsing the webhook payload. 

**Global Variables**
---------------
- **WORKFLOW_JOB**

---

<a href="../webhook_router/webhook/parse.py#L15"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `webhook_to_job`

```python
webhook_to_job(webhook: dict) → Job
```

Parse a raw json payload and extract the required information. 



**Args:**
 
 - <b>`webhook`</b>:  The webhook in json to parse. 



**Returns:**
 The parsed Job. 



**Raises:**
 
 - <b>`ParseError`</b>:  An error occurred during parsing. 


---

<a href="../webhook_router/webhook/parse.py#L11"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ParseError`
An error occurred during the parsing of the payload. 





