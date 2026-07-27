import enum


class ProductType(str, enum.Enum):
    """Where a product sits in the manufacturing lifecycle."""

    RAW = "RAW"   # Raw material
    WIP = "WIP"   # Work in progress
    FG = "FG"     # Finished good


class InventoryStatus(str, enum.Enum):
    """Current disposition of a stock record."""

    OK = "OK"     # Good / ready to sell (shown together with product type, e.g. "FG")
    RJC = "RJC"   # Rejected
    MIS = "MIS"   # Missing
    RET = "RET"   # Returned
    HLD = "HLD"   # On hold
    DMG = "DMG"   # Damaged


class LocationCategory(str, enum.Enum):
    """Distinguishes normal rack/shelf/bin storage from special oversized-item zones."""

    STANDARD = "STANDARD"  # Normal WHx-Rack-Shelf-Bin hierarchy
    SHEET = "SHEET"        # Oversized flat stock, stored at warehouse+rack level only
    PIPE = "PIPE"          # Oversized pipe stock, stored at warehouse+rack level only
    SCRAP = "SCRAP"        # Scrap / rejected-goods yard, stored at warehouse+rack level only
