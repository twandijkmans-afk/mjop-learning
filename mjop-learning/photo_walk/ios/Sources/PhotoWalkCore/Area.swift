import Foundation

/// Afronden op millimeter (half-up) en bruto oppervlak = buitenbreedte x buitenhoogte x aantal.
/// Glas wordt niet afgetrokken; vaste en draaiende delen tellen niet apart (regels 1-3).
public func roundedMillimeters(_ meters: Double) -> Decimal {
    let mm = (meters * 1000).rounded(.toNearestOrAwayFromZero)
    return Decimal(mm) / 1000
}

public func grossAreaM2(width: Decimal, height: Decimal, quantity: Int = 1) -> Decimal {
    width * height * Decimal(quantity)
}

public func decimalString(_ d: Decimal) -> String {
    var v = d
    var r = Decimal()
    NSDecimalRound(&r, &v, 6, .plain)
    return NSDecimalNumber(decimal: r).stringValue
}
