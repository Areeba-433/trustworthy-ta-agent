# Lecture 4: Stacks

A stack is a list where you add and remove
items only at the top.

## Operations

- push(x) adds x on top
- pop() removes the top item

| Operation | Cost |
|-----------|------|
| push      | O(1) |
| pop       | O(1) |

```cpp
Stack s;
s.push(1);
```

## Uses

Undo buttons and function calls both use a stack.