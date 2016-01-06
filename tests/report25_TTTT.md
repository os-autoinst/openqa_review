# 0


**Date: $now**
**Build: 0313** (reference 0311)

**Common issues:**
 * **Missing architectures**: s390x
<hr>

**Arch:** x86_64
**Status: <font color="red">Red</font>**

**New Product bugs:**




**Existing Product bugs:**



**New openQA-issues:**

* ***RAID10***: https://openqa.suse.de/tests/169785 (reference https://openqa.suse.de/tests/169590)
 * logfile: https://openqa.suse.de/tests/169785/file/autoinst-log.txt: "needle(s) 'inst-bootmenu' not found"
 * failed modules:
  * bootloader: https://openqa.suse.de/tests/169785/modules/bootloader/steps/2 (needles: bootmenu-20141112)

* ***autoyast_sle12_gnome***: https://openqa.suse.de/tests/169793 (reference https://openqa.suse.de/tests/169598)
 * logfile: https://openqa.suse.de/tests/169793/file/autoinst-log.txt: "needle(s) 'test-desktop_mainmenu-1' not found"
 * failed modules:
  * desktop_mainmenu: https://openqa.suse.de/tests/169793/modules/desktop_mainmenu/steps/1 (needles: desktop_mainmenu-gnome-20140326, desktop_mainmenu-gnome-20140813, desktop_mainmenu-gnomesled-20141205)

* ***gnome@uefi***: https://openqa.suse.de/tests/169801 (reference https://openqa.suse.de/tests/169606)
 * logfile: https://openqa.suse.de/tests/169801/file/autoinst-log.txt: "needle(s) 'languagepicked' not found"
 * failed modules:
  * welcome: https://openqa.suse.de/tests/169801/modules/welcome/steps/3 (needles: welcome-20140602)

* ***textmode***: https://openqa.suse.de/tests/169827 (reference https://openqa.suse.de/tests/169632)
 * logfile: https://openqa.suse.de/tests/169827/file/autoinst-log.txt: ">>> wait_serial: SCRIPT_FINISHED: fail"
 * failed modules:
  * snapper_undochange: https://openqa.suse.de/tests/169827/modules/snapper_undochange/steps/6

* soft fails: migration_offline_sle11_sp4_allpatterns

**Existing openQA-issues:**

* autoupgrade_sle11_sp3, cryptlvm, cryptlvm_minimal_x, migration_offline_sle11_sp3+sdk_64bit, migration_offline_sle12_sdk, sdk, sdk+allpatterns, textmode+fakescc, toolchain_zypper


---
