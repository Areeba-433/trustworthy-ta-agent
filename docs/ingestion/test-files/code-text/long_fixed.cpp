// ============================================================================
// inventory_system.cpp
// A long, realistic C++ translation unit for loader/chunker testing.
// Contains: include guards, macros, globals, enums, structs, templates,
// classes with many methods, namespaces, free functions, and main().
// ============================================================================

#ifndef INVENTORY_SYSTEM_CPP
#define INVENTORY_SYSTEM_CPP

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <unordered_map>
#include <set>
#include <algorithm>
#include <numeric>
#include <functional>
#include <memory>
#include <sstream>
#include <fstream>
#include <iomanip>
#include <ctime>
#include <chrono>
#include <random>
#include <stdexcept>
#include <optional>
#include <variant>
#include <tuple>
#include <array>
#include <deque>
#include <queue>
#include <stack>
#include <bitset>
#include <regex>
#include <thread>
#include <mutex>
#include <atomic>
#include <future>

// ---------------------------------------------------------------------------
// Global macros (big glue — these stay as their own chunk if >= 64 tokens)
// ---------------------------------------------------------------------------
#define APP_NAME "InventorySystem"
#define APP_VERSION_MAJOR 3
#define APP_VERSION_MINOR 7
#define APP_VERSION_PATCH 2
#define APP_VERSION_STRING "3.7.2"
#define LOG_INFO(msg)  std::cout << "[INFO]  " << msg << std::endl
#define LOG_WARN(msg)  std::cout << "[WARN]  " << msg << std::endl
#define LOG_ERROR(msg) std::cerr << "[ERROR] " << msg << std::endl
#define LOG_DEBUG(msg) do { if (g_debug_enabled) std::cout << "[DEBUG] " << msg << std::endl; } while (0)
#define SAFE_DELETE(p) do { delete (p); (p) = nullptr; } while (0)
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define CLAMP(v, lo, hi) MIN(MAX((v), (lo)), (hi))
#define UNUSED(x) (void)(x)
#define STRINGIFY(x) #x
#define TOSTRING(x) STRINGIFY(x)
#define VERSION_STRING TOSTRING(APP_VERSION_MAJOR) "." TOSTRING(APP_VERSION_MINOR) "." TOSTRING(APP_VERSION_PATCH)

// ---------------------------------------------------------------------------
// Global constants and variables (big glue)
// ---------------------------------------------------------------------------
namespace inventory {

constexpr int    kMaxItemsPerOrder      = 500;
constexpr int    kMaxWarehouses         = 32;
constexpr int    kDefaultRestockLevel   = 25;
constexpr int    kLowStockThreshold     = 10;
constexpr double kDefaultTaxRate        = 0.17;
constexpr double kDefaultDiscountRate   = 0.05;
constexpr int    kMaxRetries            = 3;
constexpr int    kPageSize              = 50;

bool g_debug_enabled = false;
int  g_next_order_id = 1000;
int  g_next_item_id  = 1;
std::mutex g_log_mutex;
std::atomic<int> g_operation_count{0};

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------
enum class ItemCategory {
    Electronics,
    Groceries,
    Clothing,
    Furniture,
    Toys,
    Books,
    Automotive,
    Pharmaceuticals,
    Unknown
};

enum class OrderStatus {
    Draft,
    Pending,
    Confirmed,
    Packed,
    Shipped,
    Delivered,
    Cancelled,
    Returned,
    Refunded
};

enum class WarehouseZone {
    A, B, C, D, E, Cold, Hazmat
};

enum class PaymentMethod {
    Cash, CreditCard, DebitCard, BankTransfer, DigitalWallet, Crypto
};

enum class Currency {
    PKR, USD, EUR, GBP, INR, AED
};

// ---------------------------------------------------------------------------
// Structs
// ---------------------------------------------------------------------------
struct Address {
    std::string street;
    std::string city;
    std::string state;
    std::string postal_code;
    std::string country;

    std::string to_string() const {
        std::ostringstream oss;
        oss << street << ", " << city << ", " << state << " "
            << postal_code << ", " << country;
        return oss.str();
    }

    bool is_valid() const {
        return !street.empty() && !city.empty() && !country.empty();
    }
};

struct Dimensions {
    double length_cm;
    double width_cm;
    double height_cm;

    double volume() const {
        return length_cm * width_cm * height_cm;
    }

    bool fits_in(const Dimensions& box) const {
        return length_cm <= box.length_cm &&
               width_cm  <= box.width_cm  &&
               height_cm <= box.height_cm;
    }
};

struct Money {
    Currency currency;
    long long amount_minor; // stored in paisa/cents

    double as_major() const {
        return static_cast<double>(amount_minor) / 100.0;
    }

    Money operator+(const Money& other) const {
        if (currency != other.currency) {
            throw std::invalid_argument("Currency mismatch in Money::operator+");
        }
        return {currency, amount_minor + other.amount_minor};
    }

    Money operator-(const Money& other) const {
        if (currency != other.currency) {
            throw std::invalid_argument("Currency mismatch in Money::operator-");
        }
        return {currency, amount_minor - other.amount_minor};
    }

    Money operator*(double factor) const {
        return {currency, static_cast<long long>(amount_minor * factor)};
    }
};

struct DateRange {
    std::time_t start;
    std::time_t end;

    bool contains(std::time_t t) const {
        return t >= start && t <= end;
    }

    long long days() const {
        return (end - start) / (60 * 60 * 24);
    }
};

struct ContactInfo {
    std::string email;
    std::string phone;
    std::string fax;

    bool has_email() const { return email.find('@') != std::string::npos; }
};

struct AuditEntry {
    std::string user;
    std::string action;
    std::time_t timestamp;
    std::string details;
};

// ---------------------------------------------------------------------------
// Template utilities
// ---------------------------------------------------------------------------
template <typename T>
T clamp_value(T v, T lo, T hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

template <typename T>
std::string join(const std::vector<T>& items, const std::string& sep) {
    std::ostringstream oss;
    for (size_t i = 0; i < items.size(); ++i) {
        if (i) oss << sep;
        oss << items[i];
    }
    return oss.str();
}

template <typename K, typename V>
std::vector<K> map_keys(const std::map<K, V>& m) {
    std::vector<K> keys;
    keys.reserve(m.size());
    for (const auto& kv : m) keys.push_back(kv.first);
    return keys;
}

template <typename T>
class RingBuffer {
public:
    explicit RingBuffer(size_t capacity) : capacity_(capacity), head_(0) {}

    void push(const T& value) {
        if (buffer_.size() < capacity_) {
            buffer_.push_back(value);
        } else {
            buffer_[head_] = value;
            head_ = (head_ + 1) % capacity_;
        }
    }

    std::vector<T> snapshot() const {
        std::vector<T> out;
        out.reserve(buffer_.size());
        for (size_t i = 0; i < buffer_.size(); ++i) {
            out.push_back(buffer_[(head_ + i) % buffer_.size()]);
        }
        return out;
    }

    size_t size() const { return buffer_.size(); }
    bool empty() const { return buffer_.empty(); }

private:
    size_t capacity_;
    size_t head_;
    std::vector<T> buffer_;
};

// ---------------------------------------------------------------------------
// Class: Item
// ---------------------------------------------------------------------------
class Item {
public:
    Item() = default;

    Item(int id, const std::string& sku, const std::string& name,
         ItemCategory category, Money price, int quantity)
        : id_(id), sku_(sku), name_(name), category_(category),
          price_(price), quantity_(quantity) {}

    int id() const { return id_; }
    const std::string& sku() const { return sku_; }
    const std::string& name() const { return name_; }
    ItemCategory category() const { return category_; }
    Money price() const { return price_; }
    int quantity() const { return quantity_; }
    const Dimensions& dimensions() const { return dimensions_; }
    const Address& origin() const { return origin_; }

    void set_name(const std::string& name) { name_ = name; }
    void set_price(Money price) { price_ = price; }
    void set_dimensions(const Dimensions& d) { dimensions_ = d; }
    void set_origin(const Address& a) { origin_ = a; }

    void add_stock(int n) {
        if (n < 0) throw std::invalid_argument("Cannot add negative stock");
        quantity_ += n;
    }

    bool remove_stock(int n) {
        if (n < 0) throw std::invalid_argument("Cannot remove negative stock");
        if (quantity_ < n) return false;
        quantity_ -= n;
        return true;
    }

    bool is_low_stock() const {
        return quantity_ <= kLowStockThreshold;
    }

    Money total_value() const {
        return {price_.currency, price_.amount_minor * quantity_};
    }

    std::string to_string() const {
        std::ostringstream oss;
        oss << "Item(" << id_ << ", " << sku_ << ", " << name_
            << ", qty=" << quantity_ << ", price=" << price_.as_major() << ")";
        return oss.str();
    }

    bool operator<(const Item& other) const { return id_ < other.id_; }
    bool operator==(const Item& other) const { return id_ == other.id_; }

private:
    int id_ = 0;
    std::string sku_;
    std::string name_;
    ItemCategory category_ = ItemCategory::Unknown;
    Money price_{Currency::PKR, 0};
    int quantity_ = 0;
    Dimensions dimensions_{0, 0, 0};
    Address origin_{};
};

// ---------------------------------------------------------------------------
// Class: Warehouse
// ---------------------------------------------------------------------------
class Warehouse {
public:
    Warehouse(int id, const std::string& name, const Address& location)
        : id_(id), name_(name), location_(location) {}

    int id() const { return id_; }
    const std::string& name() const { return name_; }
    const Address& location() const { return location_; }

    bool add_item(const Item& item, int quantity) {
        if (quantity <= 0) return false;
        auto it = stock_.find(item.id());
        if (it == stock_.end()) {
            stock_[item.id()] = quantity;
        } else {
            it->second += quantity;
        }
        item_index_[item.id()] = item;
        return true;
    }

    bool remove_item(int item_id, int quantity) {
        auto it = stock_.find(item_id);
        if (it == stock_.end() || it->second < quantity) return false;
        it->second -= quantity;
        if (it->second == 0) {
            stock_.erase(it);
            item_index_.erase(item_id);
        }
        return true;
    }

    int quantity_of(int item_id) const {
        auto it = stock_.find(item_id);
        return it == stock_.end() ? 0 : it->second;
    }

    std::vector<Item> low_stock_items() const {
        std::vector<Item> out;
        for (const auto& kv : stock_) {
            if (kv.second <= kLowStockThreshold) {
                auto idx = item_index_.find(kv.first);
                if (idx != item_index_.end()) out.push_back(idx->second);
            }
        }
        return out;
    }

    Money total_inventory_value() const {
        Money total{Currency::PKR, 0};
        for (const auto& kv : item_index_) {
            total = total + kv.second.total_value();
        }
        return total;
    }

    size_t distinct_items() const { return stock_.size(); }
    int total_units() const {
        int sum = 0;
        for (const auto& kv : stock_) sum += kv.second;
        return sum;
    }

    std::map<int, int> snapshot() const { return stock_; }

private:
    int id_;
    std::string name_;
    Address location_;
    std::map<int, int> stock_;
    std::map<int, Item> item_index_;
};

// ---------------------------------------------------------------------------
// Class: Customer
// ---------------------------------------------------------------------------
class Customer {
public:
    Customer(int id, const std::string& name, const ContactInfo& contact,
             const Address& billing, const Address& shipping)
        : id_(id), name_(name), contact_(contact),
          billing_(billing), shipping_(shipping) {}

    int id() const { return id_; }
    const std::string& name() const { return name_; }
    const ContactInfo& contact() const { return contact_; }
    const Address& billing_address() const { return billing_; }
    const Address& shipping_address() const { return shipping_; }

    void set_contact(const ContactInfo& c) { contact_ = c; }
    void set_billing(const Address& a) { billing_ = a; }
    void set_shipping(const Address& a) { shipping_ = a; }

    void add_loyalty_points(int points) {
        if (points < 0) throw std::invalid_argument("Negative points");
        loyalty_points_ += points;
    }

    bool redeem_loyalty_points(int points) {
        if (points < 0 || loyalty_points_ < points) return false;
        loyalty_points_ -= points;
        return true;
    }

    int loyalty_points() const { return loyalty_points_; }

    void add_order_id(int order_id) {
        order_history_.push_back(order_id);
    }

    const std::vector<int>& order_history() const { return order_history_; }

    bool is_vip() const { return loyalty_points_ >= 1000; }

    std::string to_string() const {
        std::ostringstream oss;
        oss << "Customer(" << id_ << ", " << name_
            << ", points=" << loyalty_points_ << ")";
        return oss.str();
    }

private:
    int id_;
    std::string name_;
    ContactInfo contact_;
    Address billing_;
    Address shipping_;
    int loyalty_points_ = 0;
    std::vector<int> order_history_;
};

// ---------------------------------------------------------------------------
// Class: OrderLine
// ---------------------------------------------------------------------------
class OrderLine {
public:
    OrderLine(int item_id, const std::string& sku, int quantity, Money unit_price)
        : item_id_(item_id), sku_(sku), quantity_(quantity), unit_price_(unit_price) {}

    int item_id() const { return item_id_; }
    const std::string& sku() const { return sku_; }
    int quantity() const { return quantity_; }
    Money unit_price() const { return unit_price_; }

    Money line_total() const {
        return {unit_price_.currency, unit_price_.amount_minor * quantity_};
    }

    void apply_discount(double rate) {
        double factor = 1.0 - clamp_value(rate, 0.0, 1.0);
        unit_price_ = unit_price_ * factor;
    }

private:
    int item_id_;
    std::string sku_;
    int quantity_;
    Money unit_price_;
};

// ---------------------------------------------------------------------------
// Class: Order
// ---------------------------------------------------------------------------
class Order {
public:
    explicit Order(int id, int customer_id)
        : id_(id), customer_id_(customer_id) {}

    int id() const { return id_; }
    int customer_id() const { return customer_id_; }
    OrderStatus status() const { return status_; }
    void set_status(OrderStatus s) { status_ = s; }

    void add_line(const OrderLine& line) {
        if (lines_.size() >= static_cast<size_t>(kMaxItemsPerOrder)) {
            throw std::runtime_error("Order exceeds maximum line count");
        }
        lines_.push_back(line);
    }

    const std::vector<OrderLine>& lines() const { return lines_; }

    Money subtotal() const {
        Money total{Currency::PKR, 0};
        for (const auto& line : lines_) total = total + line.line_total();
        return total;
    }

    Money tax() const {
        return subtotal() * kDefaultTaxRate;
    }

    Money discount() const {
        return subtotal() * kDefaultDiscountRate;
    }

    Money grand_total() const {
        return subtotal() + tax() - discount();
    }

    bool is_empty() const { return lines_.empty(); }

    bool can_cancel() const {
        return status_ == OrderStatus::Draft ||
               status_ == OrderStatus::Pending ||
               status_ == OrderStatus::Confirmed;
    }

    void cancel() {
        if (!can_cancel()) throw std::runtime_error("Order cannot be cancelled");
        status_ = OrderStatus::Cancelled;
    }

    std::string to_string() const {
        std::ostringstream oss;
        oss << "Order(" << id_ << ", customer=" << customer_id_
            << ", lines=" << lines_.size() << ", total=" << grand_total().as_major() << ")";
        return oss.str();
    }

private:
    int id_;
    int customer_id_;
    OrderStatus status_ = OrderStatus::Draft;
    std::vector<OrderLine> lines_;
};

// ---------------------------------------------------------------------------
// Class: InventoryService
// ---------------------------------------------------------------------------
class InventoryService {
public:
    InventoryService() = default;

    void add_warehouse(const Warehouse& w) {
        warehouses_[w.id()] = w;
    }

    void add_customer(const Customer& c) {
        customers_[c.id()] = c;
    }

    bool add_item_to_warehouse(int warehouse_id, const Item& item, int qty) {
        auto it = warehouses_.find(warehouse_id);
        if (it == warehouses_.end()) return false;
        return it->second.add_item(item, qty);
    }

    bool remove_item_from_warehouse(int warehouse_id, int item_id, int qty) {
        auto it = warehouses_.find(warehouse_id);
        if (it == warehouses_.end()) return false;
        return it->second.remove_item(item_id, qty);
    }

    int total_quantity(int item_id) const {
        int sum = 0;
        for (const auto& kv : warehouses_) sum += kv.second.quantity_of(item_id);
        return sum;
    }

    std::vector<Item> low_stock_across_warehouses() const {
        std::vector<Item> out;
        for (const auto& kv : warehouses_) {
            auto low = kv.second.low_stock_items();
            out.insert(out.end(), low.begin(), low.end());
        }
        return out;
    }

    Money total_inventory_value() const {
        Money total{Currency::PKR, 0};
        for (const auto& kv : warehouses_) {
            total = total + kv.second.total_inventory_value();
        }
        return total;
    }

    int create_order(int customer_id) {
        auto it = customers_.find(customer_id);
        if (it == customers_.end()) throw std::runtime_error("Unknown customer");
        int id = g_next_order_id++;
        Order order(id, customer_id);
        orders_[id] = order;
        it->second.add_order_id(id);
        return id;
    }

    Order* get_order(int order_id) {
        auto it = orders_.find(order_id);
        return it == orders_.end() ? nullptr : &it->second;
    }

    bool confirm_order(int order_id) {
        auto* o = get_order(order_id);
        if (!o || o->status() != OrderStatus::Draft) return false;
        o->set_status(OrderStatus::Confirmed);
        return true;
    }

    std::vector<Order> orders_by_status(OrderStatus s) const {
        std::vector<Order> out;
        for (const auto& kv : orders_) {
            if (kv.second.status() == s) out.push_back(kv.second);
        }
        return out;
    }

    size_t warehouse_count() const { return warehouses_.size(); }
    size_t customer_count() const { return customers_.size(); }
    size_t order_count() const { return orders_.size(); }

private:
    std::map<int, Warehouse> warehouses_;
    std::map<int, Customer> customers_;
    std::map<int, Order> orders_;
};

// ---------------------------------------------------------------------------
// Class: ReportGenerator
// ---------------------------------------------------------------------------
class ReportGenerator {
public:
    explicit ReportGenerator(const InventoryService& svc) : svc_(svc) {}

    std::string generate_summary() const {
        std::ostringstream oss;
        oss << "=== Inventory Summary ===\n";
        oss << "Warehouses: " << svc_.warehouse_count() << "\n";
        oss << "Customers:  " << svc_.customer_count() << "\n";
        oss << "Orders:     " << svc_.order_count() << "\n";
        oss << "Total value: " << svc_.total_inventory_value().as_major() << "\n";
        return oss.str();
    }

    std::string generate_low_stock_report() const {
        std::ostringstream oss;
        oss << "=== Low Stock Report ===\n";
        auto low = svc_.low_stock_across_warehouses();
        for (const auto& item : low) {
            oss << item.to_string() << "\n";
        }
        if (low.empty()) oss << "(none)\n";
        return oss.str();
    }

    std::string generate_orders_report(OrderStatus status) const {
        std::ostringstream oss;
        oss << "=== Orders Report (" << static_cast<int>(status) << ") ===\n";
        auto orders = svc_.orders_by_status(status);
        for (const auto& o : orders) oss << o.to_string() << "\n";
        if (orders.empty()) oss << "(none)\n";
        return oss.str();
    }

private:
    const InventoryService& svc_;
};

// ---------------------------------------------------------------------------
// Class: CsvExporter
// ---------------------------------------------------------------------------
class CsvExporter {
public:
    static std::string escape(const std::string& field) {
        if (field.find_first_of(",\"\n") == std::string::npos) return field;
        std::string out = "\"";
        for (char c : field) {
            if (c == '"') out += "\"\"";
            else out += c;
        }
        out += "\"";
        return out;
    }

    static std::string row(const std::vector<std::string>& fields) {
        std::ostringstream oss;
        for (size_t i = 0; i < fields.size(); ++i) {
            if (i) oss << ",";
            oss << escape(fields[i]);
        }
        return oss.str();
    }

    static std::string items_to_csv(const std::vector<Item>& items) {
        std::ostringstream oss;
        oss << "id,sku,name,category,quantity,price\n";
        for (const auto& item : items) {
            oss << row({std::to_string(item.id()), item.sku(), item.name(),
                        std::to_string(static_cast<int>(item.category())),
                        std::to_string(item.quantity()),
                        std::to_string(item.price().as_major())}) << "\n";
        }
        return oss.str();
    }
};

// ---------------------------------------------------------------------------
// Class: AuditLog
// ---------------------------------------------------------------------------
class AuditLog {
public:
    void record(const std::string& user, const std::string& action,
                const std::string& details) {
        std::lock_guard<std::mutex> lock(mutex_);
        entries_.push_back({user, action, std::time(nullptr), details});
    }

    std::vector<AuditEntry> entries_for(const std::string& user) const {
        std::vector<AuditEntry> out;
        for (const auto& e : entries_) {
            if (e.user == user) out.push_back(e);
        }
        return out;
    }

    size_t size() const { return entries_.size(); }

private:
    mutable std::mutex mutex_;
    std::vector<AuditEntry> entries_;
};

}  // namespace inventory

// ---------------------------------------------------------------------------
// Free functions (many, to exercise the chunker)
// ---------------------------------------------------------------------------
namespace inventory {

std::string category_to_string(ItemCategory c) {
    switch (c) {
        case ItemCategory::Electronics:    return "Electronics";
        case ItemCategory::Groceries:      return "Groceries";
        case ItemCategory::Clothing:       return "Clothing";
        case ItemCategory::Furniture:      return "Furniture";
        case ItemCategory::Toys:           return "Toys";
        case ItemCategory::Books:          return "Books";
        case ItemCategory::Automotive:     return "Automotive";
        case ItemCategory::Pharmaceuticals:return "Pharmaceuticals";
        default:                           return "Unknown";
    }
}

ItemCategory category_from_string(const std::string& s) {
    if (s == "Electronics") return ItemCategory::Electronics;
    if (s == "Groceries") return ItemCategory::Groceries;
    if (s == "Clothing") return ItemCategory::Clothing;
    if (s == "Furniture") return ItemCategory::Furniture;
    if (s == "Toys") return ItemCategory::Toys;
    if (s == "Books") return ItemCategory::Books;
    if (s == "Automotive") return ItemCategory::Automotive;
    if (s == "Pharmaceuticals") return ItemCategory::Pharmaceuticals;
    return ItemCategory::Unknown;
}

std::string status_to_string(OrderStatus s) {
    switch (s) {
        case OrderStatus::Draft:     return "Draft";
        case OrderStatus::Pending:   return "Pending";
        case OrderStatus::Confirmed: return "Confirmed";
        case OrderStatus::Packed:    return "Packed";
        case OrderStatus::Shipped:   return "Shipped";
        case OrderStatus::Delivered: return "Delivered";
        case OrderStatus::Cancelled: return "Cancelled";
        case OrderStatus::Returned:  return "Returned";
        case OrderStatus::Refunded:  return "Refunded";
        default:                     return "Unknown";
    }
}

std::string currency_to_string(Currency c) {
    switch (c) {
        case Currency::PKR: return "PKR";
        case Currency::USD: return "USD";
        case Currency::EUR: return "EUR";
        case Currency::GBP: return "GBP";
        case Currency::INR: return "INR";
        case Currency::AED: return "AED";
        default:            return "???";
    }
}

Money convert_currency(Money m, Currency target, double rate) {
    if (m.currency == target) return m;
    long long converted = static_cast<long long>(m.amount_minor * rate);
    return {target, converted};
}

std::string format_money(Money m) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(2)
        << m.as_major() << " " << currency_to_string(m.currency);
    return oss.str();
}

std::vector<Item> filter_by_category(const std::vector<Item>& items, ItemCategory c) {
    std::vector<Item> out;
    for (const auto& i : items) if (i.category() == c) out.push_back(i);
    return out;
}

std::vector<Item> filter_low_stock(const std::vector<Item>& items) {
    std::vector<Item> out;
    for (const auto& i : items) if (i.is_low_stock()) out.push_back(i);
    return out;
}

std::vector<Item> sort_by_price(std::vector<Item> items, bool ascending = true) {
    std::sort(items.begin(), items.end(), [ascending](const Item& a, const Item& b) {
        return ascending ? a.price().as_major() < b.price().as_major()
                         : a.price().as_major() > b.price().as_major();
    });
    return items;
}

std::vector<Item> sort_by_quantity(std::vector<Item> items) {
    std::sort(items.begin(), items.end(), [](const Item& a, const Item& b) {
        return a.quantity() < b.quantity();
    });
    return items;
}

double average_price(const std::vector<Item>& items) {
    if (items.empty()) return 0.0;
    double sum = 0.0;
    for (const auto& i : items) sum += i.price().as_major();
    return sum / items.size();
}

Item* find_item_by_sku(std::vector<Item>& items, const std::string& sku) {
    for (auto& i : items) if (i.sku() == sku) return &i;
    return nullptr;
}

bool validate_address(const Address& a) {
    if (!a.is_valid()) return false;
    if (a.postal_code.size() < 4) return false;
    return true;
}

bool validate_contact(const ContactInfo& c) {
    if (!c.email.empty() && !c.has_email()) return false;
    if (!c.phone.empty() && c.phone.size() < 7) return false;
    return true;
}

int generate_random_int(int lo, int hi) {
    static std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<int> dist(lo, hi);
    return dist(rng);
}

double generate_random_double(double lo, double hi) {
    static std::mt19937 rng(std::random_device{}());
    std::uniform_real_distribution<double> dist(lo, hi);
    return dist(rng);
}

std::string current_timestamp() {
    std::time_t now = std::time(nullptr);
    char buf[64];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&now));
    return std::string(buf);
}

std::vector<std::string> split_string(const std::string& s, char delim) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string token;
    while (std::getline(ss, token, delim)) out.push_back(token);
    return out;
}

std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

std::string to_upper(const std::string& s) {
    std::string out = s;
    std::transform(out.begin(), out.end(), out.begin(), ::toupper);
    return out;
}

std::string to_lower(const std::string& s) {
    std::string out = s;
    std::transform(out.begin(), out.end(), out.begin(), ::tolower);
    return out;
}

bool starts_with(const std::string& s, const std::string& prefix) {
    return s.size() >= prefix.size() && s.compare(0, prefix.size(), prefix) == 0;
}

bool ends_with(const std::string& s, const std::string& suffix) {
    return s.size() >= suffix.size() &&
           s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// A deliberately long function (> 512 tokens) to trigger split_to_fit()
Money compute_discounted_total(const std::vector<OrderLine>& lines,
                               double base_discount,
                               double loyalty_discount,
                               double seasonal_discount,
                               double bulk_discount,
                               bool apply_tax,
                               Currency target_currency,
                               double exchange_rate) {
    Money total{Currency::PKR, 0};

    for (const auto& line : lines) {
        Money line_total = line.line_total();

        // Apply base discount
        double factor = 1.0 - clamp_value(base_discount, 0.0, 1.0);
        line_total = line_total * factor;

        // Apply loyalty discount
        factor = 1.0 - clamp_value(loyalty_discount, 0.0, 1.0);
        line_total = line_total * factor;

        // Apply seasonal discount
        factor = 1.0 - clamp_value(seasonal_discount, 0.0, 1.0);
        line_total = line_total * factor;

        // Apply bulk discount only if quantity is high
        if (line.quantity() >= 100) {
            factor = 1.0 - clamp_value(bulk_discount, 0.0, 1.0);
            line_total = line_total * factor;
        } else if (line.quantity() >= 50) {
            factor = 1.0 - clamp_value(bulk_discount * 0.5, 0.0, 1.0);
            line_total = line_total * factor;
        } else if (line.quantity() >= 10) {
            factor = 1.0 - clamp_value(bulk_discount * 0.25, 0.0, 1.0);
            line_total = line_total * factor;
        }

        total = total + line_total;
    }

    if (apply_tax) {
        total = total + total * kDefaultTaxRate;
    }

    if (target_currency != Currency::PKR) {
        total = convert_currency(total, target_currency, exchange_rate);
    }

    return total;
}

// Another long function
std::vector<Item> build_sample_catalog() {
    std::vector<Item> catalog;
    catalog.reserve(20);

    catalog.emplace_back(1, "SKU-001", "Laptop Pro 15", ItemCategory::Electronics,
                         Money{Currency::PKR, 25000000}, 12);
    catalog.emplace_back(2, "SKU-002", "Wireless Mouse", ItemCategory::Electronics,
                         Money{Currency::PKR, 350000}, 150);
    catalog.emplace_back(3, "SKU-003", "Mechanical Keyboard", ItemCategory::Electronics,
                         Money{Currency::PKR, 1200000}, 80);
    catalog.emplace_back(4, "SKU-004", "27-inch Monitor", ItemCategory::Electronics,
                         Money{Currency::PKR, 5500000}, 30);
    catalog.emplace_back(5, "SKU-005", "USB-C Hub", ItemCategory::Electronics,
                         Money{Currency::PKR, 450000}, 200);
    catalog.emplace_back(6, "SKU-006", "Basmati Rice 5kg", ItemCategory::Groceries,
                         Money{Currency::PKR, 250000}, 500);
    catalog.emplace_back(7, "SKU-007", "Cooking Oil 1L", ItemCategory::Groceries,
                         Money{Currency::PKR, 80000}, 300);
    catalog.emplace_back(8, "SKU-008", "Tea Leaves 500g", ItemCategory::Groceries,
                         Money{Currency::PKR, 120000}, 250);
    catalog.emplace_back(9, "SKU-009", "Cotton T-Shirt", ItemCategory::Clothing,
                         Money{Currency::PKR, 150000}, 400);
    catalog.emplace_back(10, "SKU-010", "Denim Jeans", ItemCategory::Clothing,
                         Money{Currency::PKR, 350000}, 220);
    catalog.emplace_back(11, "SKU-011", "Running Shoes", ItemCategory::Clothing,
                         Money{Currency::PKR, 650000}, 90);
    catalog.emplace_back(12, "SKU-012", "Office Chair", ItemCategory::Furniture,
                         Money{Currency::PKR, 1800000}, 40);
    catalog.emplace_back(13, "SKU-013", "Study Desk", ItemCategory::Furniture,
                         Money{Currency::PKR, 2200000}, 25);
    catalog.emplace_back(14, "SKU-014", "Bookshelf", ItemCategory::Furniture,
                         Money{Currency::PKR, 1500000}, 35);
    catalog.emplace_back(15, "SKU-015", "Remote Control Car", ItemCategory::Toys,
                         Money{Currency::PKR, 200000}, 120);
    catalog.emplace_back(16, "SKU-016", "Building Blocks Set", ItemCategory::Toys,
                         Money{Currency::PKR, 300000}, 75);
    catalog.emplace_back(17, "SKU-017", "C++ Primer 5th Ed", ItemCategory::Books,
                         Money{Currency::PKR, 800000}, 60);
    catalog.emplace_back(18, "SKU-018", "Design Patterns", ItemCategory::Books,
                         Money{Currency::PKR, 950000}, 45);
    catalog.emplace_back(19, "SKU-019", "Car Battery", ItemCategory::Automotive,
                         Money{Currency::PKR, 1200000}, 20);
    catalog.emplace_back(20, "SKU-020", "Engine Oil 4L", ItemCategory::Automotive,
                         Money{Currency::PKR, 400000}, 55);

    return catalog;
}

} // namespace inventory

// ---------------------------------------------------------------------------
// main()
// ---------------------------------------------------------------------------
int main() {
    using namespace inventory;

    LOG_INFO("Starting " << APP_NAME << " v" << VERSION_STRING);

    // Build a sample catalog
    auto catalog = build_sample_catalog();
    LOG_INFO("Catalog size: " << catalog.size());

    // Create warehouses
    Warehouse w1(1, "Karachi Main", {"Plot 12, I.I. Chundrigar", "Karachi", "Sindh", "74000", "Pakistan"});
    Warehouse w2(2, "Lahore Depot", {"45 Ferozepur Road", "Lahore", "Punjab", "54000", "Pakistan"});

    for (const auto& item : catalog) {
        w1.add_item(item, item.quantity() / 2);
        w2.add_item(item, item.quantity() / 2);
    }

    // Create customers
    Customer c1(101, "Ali Khan",
                {"ali@example.com", "+92-300-1234567", ""},
                {"Street 1", "Karachi", "Sindh", "74000", "Pakistan"},
                {"Street 1", "Karachi", "Sindh", "74000", "Pakistan"});
    Customer c2(102, "Sara Ahmed",
                {"sara@example.com", "+92-321-7654321", ""},
                {"Street 2", "Lahore", "Punjab", "54000", "Pakistan"},
                {"Street 2", "Lahore", "Punjab", "54000", "Pakistan"});

    c1.add_loyalty_points(1500); // VIP
    c2.add_loyalty_points(300);

    // Inventory service
    InventoryService svc;
    svc.add_warehouse(w1);
    svc.add_warehouse(w2);
    svc.add_customer(c1);
    svc.add_customer(c2);

    // Create an order
    int order_id = svc.create_order(c1.id());
    Order* order = svc.get_order(order_id);
    if (order) {
        order->add_line(OrderLine(1, "SKU-001", 2, Money{Currency::PKR, 25000000}));
        order->add_line(OrderLine(2, "SKU-002", 5, Money{Currency::PKR, 350000}));
        order->add_line(OrderLine(17, "SKU-017", 3, Money{Currency::PKR, 800000}));
        svc.confirm_order(order_id);
        LOG_INFO("Order " << order_id << ": " << order->to_string());
    }

    // Reports
    ReportGenerator reporter(svc);
    std::cout << reporter.generate_summary();
    std::cout << reporter.generate_low_stock_report();
    std::cout << reporter.generate_orders_report(OrderStatus::Confirmed);

    // CSV export
    std::cout << "\n=== CSV Export (first 5 items) ===\n";
    std::vector<Item> first5(catalog.begin(), catalog.begin() + 5);
    std::cout << CsvExporter::items_to_csv(first5);

    // Long function test
    std::vector<OrderLine> test_lines = {
        OrderLine(1, "SKU-001", 120, Money{Currency::PKR, 25000000}),
        OrderLine(2, "SKU-002", 60,  Money{Currency::PKR, 350000}),
        OrderLine(3, "SKU-003", 15,  Money{Currency::PKR, 1200000}),
    };
    Money discounted = compute_discounted_total(
        test_lines, 0.05, 0.10, 0.03, 0.08, true, Currency::USD, 0.0036);
    LOG_INFO("Discounted total (USD): " << format_money(discounted));

    // Audit
    AuditLog log;
    log.record("admin", "STARTUP", "Application started");
    log.record("admin", "ORDER_CREATE", "Order " + std::to_string(order_id));
    LOG_INFO("Audit entries: " << log.size());

    LOG_INFO("Done.");
    return 0;
}

#endif // INVENTORY_SYSTEM_CPP