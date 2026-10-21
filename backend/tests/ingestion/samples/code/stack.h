#ifndef STACK_H
#define STACK_H

#include <stdexcept>

const int MAX_SIZE = 100;

// A fixed-size stack of integers.
class Stack {
public:
    Stack();
    void push(int x);
    int pop();
    bool isEmpty() const;

private:
    int data[MAX_SIZE];
    int top;
};

#endif