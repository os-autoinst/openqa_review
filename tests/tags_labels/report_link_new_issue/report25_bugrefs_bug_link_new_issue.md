# 0


**Date:** 2016-09-25 - 17:27
**Build:** 1507 (reference 1500)

**Common issues:**

 * **Missing architectures**: aarch64, i586, x86_64

---

**Arch:** arm
**Status: <span style="color: red;">Red</span>**

**Skipped Test:**

* RAID6
* cryptlvm+activate_existing
* cryptlvm+activate_existing+force_recompute
* cryptlvm+activate_existing+import_users
* cryptlvm+cancel_existing
* installcheck
* rollback_upgrade_offline_13.2
* rollback_upgrade_offline_13.2sp1
* gcc5-http
* leap+extratests
* xfs
* yast_hostname
* yast_hostname+linuxrc_hostname
* yast_no_self_update



**TODO: review**

***new issues***

* [gcc5+allpatterns](https://openqa.opensuse.org/tests/585912): report [product bug](https://bugzilla.opensuse.org/enter_bug.cgi?product=openSUSE+Tumbleweed&component=&short_desc=%5BBuild+2139%5D+openQA+test+fails&bug_file_loc=https%3A%2F%2Fopenqa.opensuse.org%2Ftests%2F585912&comment=%23%23%23+Observation%0A%0AopenQA+test+in+scenario+openSUSE-42.1-Gnome-DVD-arm-gcc5%2Ballpatterns%40arm+fails+in%0Ahttps%3A%2F%2Fopenqa.opensuse.org%2Ftests%2F585912%0A%0A%0A%23%23+Reproducible%0A%0AFails+since+%28at+least%29+Build+2139+%28current+job%29%0A%0A%0A%23%23+Expected+result%0A%0ALast+good%3A+%5B2137%5D%28https%3A%2F%2Fopenqa.opensuse.org%2Ftests%2F585767%29+%28or+more+recent%29%0A%0A%0A%23%23+Further+details%0A%0AAlways+latest+result+in+this+scenario%3A+%5Blatest%5D%28https%3A%2F%2Fopenqa.opensuse.org%2Ftests%2Flatest%3Fmachine%3Darm%26arch%3Darm%26distri%3Dopensuse%26flavor%3DGnome-DVD%26test%3Dgcc5%252Ballpatterns%26version%3D42.1%29%0A) / [openQA issue](https://progress.opensuse.org/projects/openqatests/issues/new?issue%5Bsubject%5D=%5BBuild+2139%5D+test+fails&issue%5Bdescription%5D=%23%23%23+Observation%0A%0AopenQA+test+in+scenario+openSUSE-42.1-Gnome-DVD-arm-gcc5%2Ballpatterns%40arm+fails+in%0Ahttps%3A%2F%2Fopenqa.opensuse.org%2Ftests%2F585912%0A%0A%0A%23%23+Reproducible%0A%0AFails+since+%28at+least%29+Build+2139+%28current+job%29%0A%0A%0A%23%23+Expected+result%0A%0ALast+good%3A+%5B2137%5D%28https%3A%2F%2Fopenqa.opensuse.org%2Ftests%2F585767%29+%28or+more+recent%29%0A%0A%0A%23%23+Further+details%0A%0AAlways+latest+result+in+this+scenario%3A+%5Blatest%5D%28https%3A%2F%2Fopenqa.opensuse.org%2Ftests%2Flatest%3Fmachine%3Darm%26arch%3Darm%26distri%3Dopensuse%26flavor%3DGnome-DVD%26test%3Dgcc5%252Ballpatterns%26version%3D42.1%29%0A)



---
