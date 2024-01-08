# driver_lcd_ste2007
Micropython driver for 96x68 black &amp; white LCD display utilizing the STE2007 IC

* Overrides framebuf.FrameBuffer
* Adds reset, init, contrast, invert, rotate, and sleep methods

## Notes
* rotate(180) is mirrored and needs to be fixed
* contrast setting is not functional
* There are print() debug statements