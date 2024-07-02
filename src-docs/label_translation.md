<!-- markdownlint-disable -->

<a href="../webhook_router/webhook/label_translation.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `label_translation`
Module for translating labels to flavours. 

**Global Variables**
---------------
- **WORKFLOW_JOB**
- **LABEL_SEPARATOR**

---

<a href="../webhook_router/webhook/label_translation.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `to_labels_flavor_mapping`

```python
to_labels_flavor_mapping(
    flavor_label_mapping: FlavorLabelsMapping,
    ignore_labels: set[str]
) → LabelsFlavorMapping
```

Convert the flavor label mapping to a label flavor mapping. 



**Args:**
 
 - <b>`flavor_label_mapping`</b>:  The flavor label mapping. 
 - <b>`ignore_labels`</b>:  The labels to ignore (e.g. "self-hosted" or "linux"). 



**Returns:**
 The label flavor mapping. 


---

<a href="../webhook_router/webhook/label_translation.py#L79"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `labels_to_flavor`

```python
labels_to_flavor(
    labels: set[str],
    label_flavor_mapping: LabelsFlavorMapping
) → str
```

Map the labels to a flavor. 



**Args:**
 
 - <b>`labels`</b>:  The labels to map. 
 - <b>`label_flavor_mapping`</b>:  The available flavors. 



**Raises:**
 
 - <b>`InvalidLabelCombinationError`</b>:  If the label combination is invalid. 



**Returns:**
 The flavor. 


---

<a href="../webhook_router/webhook/label_translation.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../webhook_router/webhook/label_translation.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LabelsFlavorMapping`
A class to represent the mapping of labels to flavors. 



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




---

<a href="../webhook_router/webhook/label_translation.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InvalidLabelCombinationError`
The label combination is invalid. 





