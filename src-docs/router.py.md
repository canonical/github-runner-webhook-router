<!-- markdownlint-disable -->

<a href="../webhook_router/router.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `router.py`
Module for routing webhooks to the appropriate message queue. 


---

<a href="../webhook_router/router.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `forward`

```python
forward(job: Job, route_table: LabelsFlavorMapping) → None
```

Forward the job to the appropriate message queue. 



**Args:**
 
 - <b>`job`</b>:  The job to forward. 
 - <b>`route_table`</b>:  The mapping of labels to flavors. 



**Raises:**
 
 - <b>`RouterError`</b>:  If the job cannot be forwarded. 


---

## <kbd>class</kbd> `RouterError`
Raised when a router error occurs. 





