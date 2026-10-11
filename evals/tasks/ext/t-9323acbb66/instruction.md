`World().create_entity()` does not create entity if no components are given
**Describe the bug**
As a factory method I assume it creates entity for sure but that do not happen is edge case of missing components.

**To Reproduce**
```python3
import esper

world = esper.World()
entity = world.create_entity()
assert world.entity_exists(entity)  # raises AssertionError
```
```python3
import esper

world = esper.World()
entity = world.create_entity()
assert not world.entity_exists(entity)  # not existing entity

entity_2 = world.create_entity()
assert entity_2 == 2  # Incrementing counter even though 1st one seems not to exist
```

**Expected behavior**
Imo proper behaviour is to be able to create "empty" entity and provide it with components later. Kind of how you do it with builder pattern.
Plus I've found that `add_component()` has logic for creating missing entity and that is most probably result of that bug. Following Single Responsibility Principle, that should not be part of `add_component()` method imo. See example below:
```python3
import esper

world = esper.World()
made_up_entity = 123
world.add_component(made_up_entity, None)  # Imo should raise KeyError because of missing entity
world.entity_exists(made_up_entity)  # Works just fine and should not
```

**Development environment:**
 - Python 3.11
 - Esper 2.4

**Fix proposal**
To fix that it is simple enough to pull [链接已移除] 
```python3
if entity not in self._entities:
    self._entities[entity] = {}
```
out of for loop in `create_entity()` method.
Consider removing entity creation from `add_component()` method. 

Tell me what do you think about it, I can implement change and unit tests later on
