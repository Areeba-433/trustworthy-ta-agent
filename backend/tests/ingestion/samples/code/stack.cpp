#include <iostream>
#include "stack.h"

using namespace std;

int pushCount = 0;

class Stack;

Stack::Stack() : top(-1) {}

// Add x on top of the stack.
void Stack::push(int x) {
    if (top >= MAX_SIZE - 1) {
        throw overflow_error("stack full");
    }
    data[++top] = x;
    pushCount++;
}

int Stack::pop() {
    if (isEmpty()) {
        throw underflow_error("stack empty");
    }
    return data[top--];
}

bool Stack::isEmpty() const { return top == -1; }

namespace util {

template <typename T>
T maxOf(T a, T b) {
    return a > b ? a : b;
}

struct Point {
    int x, y;
};

}  // namespace util

int main() {
    Stack s;
    s.push(1);
    s.push(2);
    cout << s.pop() << endl;
    return 0;
}