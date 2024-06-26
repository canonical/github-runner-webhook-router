<!-- markdownlint-disable -->

<a href="../webhook_router/mq.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `mq.py`
Module for interacting with the message queue. 

**Global Variables**
---------------
- **MONGODB_DB_CONNECT_STR**

---

<a href="../webhook_router/mq.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `add_job_to_queue`

```python
add_job_to_queue(job: Job, flavor: str) → None
```

Forward the webhook to the message queue. 



**Args:**
 
 - <b>`job`</b>:  The job to add to the queue. 
 - <b>`flavor`</b>:  The flavor to add the job to. 


---

<a href="../webhook_router/mq.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `can_connect`

```python
can_connect() → bool
```

Check if we can connect to the message queue. 



**Returns:**
  True if we can connect, False otherwise. 


