# cuisine.group

The `cuisine.group` module handles group operations.

Examples for methods in `group`:

- Checking if there is a group defined with the given name using the **check** method:

```python
cuisine.group.check('root')
```

-  Creating a group with the given name, and optionally given gid, using the **create** method:

```python
cuisine.group.create('admin')
```

- Ensuring that the group with the given name (and optional gid) exists using the **ensure** method:

  ```python
  cuisine.group.ensure('admin')
  ```

```
!!!
title = "Cuisine.group"
date = "2017-04-08"
tags = []
```
