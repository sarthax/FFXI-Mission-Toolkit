// From PlayOnline.FFXI.Enums (POLUtils) -- needed by FFXIEncoding's in-band elemental-symbol
// decoding, small enough to just include directly rather than pull in the rest of Enums.cs.
namespace PlayOnline.FFXI
{
    public enum Element : byte
    {
        Fire = 0x00,
        Ice = 0x01,
        Air = 0x02,
        Earth = 0x03,
        Thunder = 0x04,
        Water = 0x05,
        Light = 0x06,
        Dark = 0x07,
        Special = 0x0f,
        Undecided = 0xff,
    }
}
