<!-- markdownlint-disable -->

<a href="../webhook_router/translation.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `translation.py`
Module for parsing the webhook payload. 

**Global Variables**
---------------
- **WORKFLOW_JOB**

---

<a href="../webhook_router/translation.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `webhook_to_job`

```python
webhook_to_job(webhook: dict) → Job
```

Parse a raw json payload and extract the required information. 



**Args:**
 
 - <b>`webhook`</b>:  The webhook in json to parse. 



**Returns:**
 The Webhook object. 



**Raises:**
 
 - <b>`ParseError`</b>:  An error occurred during the translation. 


---

<a href="../webhook_router/translation.py#L83"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `labels_to_flavor`

```python
labels_to_flavor(labels: list[str], available_flavors: list[str]) → str
```

Map the labels to a flavor. 



**Args:**
 
 - <b>`labels`</b>:  The labels to map. 
 - <b>`available_flavors`</b>:  The available flavors. 



**Raises:**
 
 - <b>`MultipleFlavorError`</b>:  Multiple flavors found in labels. 



**Returns:**
 The flavor. 


---

## <kbd>class</kbd> `Job`
A class to translate the payload. 



**Attributes:**
 
 - <b>`labels`</b>:  The labels of the job. 
 - <b>`status`</b>:  The status of the job. 
 - <b>`run_url`</b>:  The URL of the job. 


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

## <kbd>class</kbd> `MultipleFlavorError`
Raised when multiple flavours are found in the labels. 





---

## <kbd>class</kbd> `ParseError`
An error occurred during the parsing of the payload. 





