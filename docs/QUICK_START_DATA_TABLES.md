# Quick Start Guide - Enhanced Data Tables

## How to Use the New Features

### 🔍 **Search**
- **Location**: Top-left control panel
- **How to use**: Type any text to search across all columns
- **Real-time**: Results filter as you type
- **Example**: Type "ABC Foods" to find all receipts from that supplier

### 📊 **Sort by Column**
- **Location**: Table headers
- **How to use**: Click on any column header (ID, Date, Supplier, Total, etc.)
- **Visual cue**: Headers show they're clickable with hover effects
- **Example**: Click "Grand Total" header to sort receipts by amount (ascending/descending)

### 🎯 **Filter by Range**
- **Location**: Top control panel (middle dropdown)
- **Receipts page**: "Filter by amount" (₹0-₹1K, ₹1K-₹5K, ₹5K-₹10K, ₹10K+)
- **Suppliers page**: "Filter by spend" (₹0-₹10K, ₹10K-₹50K, ₹50K-₹100K, ₹100K+)
- **How to use**: Select a range from dropdown
- **Example**: Select "₹10,000+" to see only high-value receipts

### 📄 **Change Page Size**
- **Location**: Top control panel (middle-right dropdown)
- **Options**: 5, 10, 25, or 50 rows per page
- **How to use**: Select number from "Rows per page" dropdown
- **Effect**: Table instantly shows selected number of rows
- **Example**: Select "50" to view 50 receipts at once

### 📋 **Pagination**
- **Location**: Bottom of table
- **Shows**: "Showing X to Y of Z entries"
- **Navigation**: First, Previous, Page numbers, Next, Last buttons
- **Auto-updates**: Changes based on search/filter results

## Control Panel Layout

```
┌─────────────────────────────────────────────────────┐
│                   Control Panel                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Search Box        │  Rows per Page  │  Amount Filter│
│  [Search...]       │  [10 ▼]         │  [All ▼]      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Combining Filters (Advanced)

You can use multiple filters together:

**Example 1 - Receipts Page**:
1. Set "Filter by amount" to "₹10,000+"
2. Type "ABC Foods" in search box
3. Change page size to "25"
4. Result: Shows up to 25 receipts from ABC Foods over ₹10,000

**Example 2 - Suppliers Page**:
1. Set "Filter by spend" to "₹100,000+"
2. Type partial phone number
3. Click "Total Spend" to sort high to low
4. Result: Shows high-spending suppliers sorted by spend

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Focus Search | Ctrl+F (then click search box) |
| Change Page Size | Tab to dropdown, arrow keys |
| Sort Column | Click header |

## Tips & Tricks

✨ **Productivity Tips**:
- Save time: Use search instead of scrolling
- Bulk view: Set page size to 50 to see more data at once
- Quick analysis: Click column headers to find highest/lowest values
- Smart filtering: Combine search + amount filter for precise results

🔄 **Data is Live**:
- No page refresh needed
- All filtering happens instantly
- Original data never changed
- Can undo filters by clearing controls

💡 **Common Use Cases**:

**"Show me all receipts from January over ₹5,000"**
1. Search: Type date or supplier name
2. Filter: Select "₹5,000 - ₹10,000" or "₹10,000+"
3. Sort: Click Voucher Date header to group by date

**"Find my top 10 suppliers by spending"**
1. Set page size to "10"
2. Filter by spend: "₹100,000+"
3. Click "Total Spend" header to sort high to low

**"Show all receipts from a specific vendor"**
1. Search: Type vendor name
2. Change page size to "50" to see all results
3. Results show matching receipts only

## Mobile-Friendly

- ✅ Works on tablets
- ✅ Works on phones (responsive design)
- ✅ Touch-friendly controls
- ✅ Automatic layout adjustment

## Notes

- Search results update as you type (no need to press Enter)
- You can change filters multiple times
- Table remembers your current page size during session
- Closing page resets to default settings

## Still Need Help?

- **Search not working?** Make sure you're typing in the search box at the top
- **Sort not working?** Click directly on column headers (hover to see they're clickable)
- **Pagination missing?** Scroll down below the table to see page controls
- **Filters not applied?** Check dropdown shows correct range selected
