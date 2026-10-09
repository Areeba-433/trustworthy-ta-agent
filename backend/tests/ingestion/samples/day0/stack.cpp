#include <vector>

// A fixed-type stack used in Lab 5.
class Stack {
public:
    void push(int x) { items.push_back(x); }
    int pop() { int x = items.back(); items.pop_back(); return x; }
private:
    std::vector<int> items;
};
