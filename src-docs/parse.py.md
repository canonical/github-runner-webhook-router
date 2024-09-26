<!-- markdownlint-disable -->

<a href="../webhook_router/parse.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `parse.py`
Module for parsing the webhook payload. 

**Global Variables**
---------------
- **WORKFLOW_JOB**

---

<a href="../webhook_router/parse.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `webhook_to_job`

```python
webhook_to_job(payload: dict, ignore_labels: Collection[str]) → Job
```

Parse a raw json payload and extract the required information. 



**Args:**
 
 - <b>`payload`</b>:  The webhook's payload in json to parse. 
 - <b>`ignore_labels`</b>:  The labels to ignore when parsing. For example, "self-hosted" or "linux". 



**Returns:**
 The parsed Job. 



**Raises:**
 
 - <b>`ParseError`</b>:  An error occurred during parsing. 


---

## <kbd>class</kbd> `Job`
A class to translate the payload. 



**Attributes:**
 
 - <b>`labels`</b>:  The labels of the job. 
 - <b>`status`</b>:  The status of the job. 
 - <b>`url`</b>:  The URL of the job to be able to check its status. 


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 




---

## <kbd>class</kbd> `JobStatus`
The status of the job. 



**Attributes:**
 
 - <b>`COMPLETED`</b>:  The job is completed. 
 - <b>`IN_PROGRESS`</b>:  The job is in progress. 
 - <b>`QUEUED`</b>:  The job is queued. 
 - <b>`WAITING`</b>:  The job is waiting. 





---

## <kbd>class</kbd> `ParseError`
An error occurred during the parsing of the payload. 





---

## <kbd>class</kbd> `ValidationResult`
ValidationResult(is_valid, msg) 





