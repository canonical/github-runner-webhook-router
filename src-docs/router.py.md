<!-- markdownlint-disable -->

<a href="../webhook_router/router.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `router.py`
Module for routing webhooks to the appropriate message queue. 

**Global Variables**
---------------
- **WORKFLOW_JOB**
- **LABEL_SEPARATOR**

---

<a href="../webhook_router/router.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `to_routing_table`

```python
to_routing_table(
    flavor_label_mapping: FlavorLabelsMapping,
    ignore_labels: set[str]
) → RoutingTable
```

Convert the flavor label mapping to a route table. 



**Args:**
 
 - <b>`flavor_label_mapping`</b>:  The flavor label mapping. 
 - <b>`ignore_labels`</b>:  The labels to ignore (e.g. "self-hosted" or "linux"). 



**Returns:**
 The label flavor mapping. 


---

<a href="../webhook_router/router.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `forward`

```python
forward(job: Job, routing_table: RoutingTable) → None
```

Forward the job to the appropriate message queue. 



**Args:**
 
 - <b>`job`</b>:  The job to forward. 
 - <b>`routing_table`</b>:  The mapping of labels to flavors. 



**Raises:**
 
 - <b>`RouterError`</b>:  If the job cannot be forwarded. 


---

## <kbd>class</kbd> `FlavorLabelsMapping`
A class to represent the mapping of flavors to labels. 



**Attributes:**
 
 - <b>`mapping`</b>:  The mapping of flavors to labels. 


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

## <kbd>class</kbd> `RouterError`
Raised when a router error occurs. 





---

## <kbd>class</kbd> `RoutingTable`
A class to represent how to route jobs to the appropriate message queue. 



**Attributes:**
 
 - <b>`mapping`</b>:  The mapping of labels to flavors. 
 - <b>`ignore_labels`</b>:  The labels to ignore (e.g. "self-hosted" or "linux"). 
 - <b>`default_flavor`</b>:  The default flavor. 


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




