from JumpScale import j


base = j.tools.cuisine._getBaseClass()


class CuisineXRDP(base):

    def build(self):
        """
        builds a full xrdp, this can take a while
        """
        C = """
        cd /root
        git clone https://github.com/scarygliders/X11RDP-o-Matic.git
        cd X11RDP-o-Matic
        bash X11rdp-o-matic.sh
        ln -fs /usr/bin/Xvfb /etc/X11/X
        apt-get update
        apt-get install  -y --force-yes lxde lxtask
        echo 'pgrep -U $(id -u) lxsession | grep -v ^$_LXSESSION_PID | xargs --no-run-if-empty kill' > /bin/lxcleanup.sh
        chmod +x /bin/lxcleanup.sh
        echo '@lxcleanup.sh' >> /etc/xdg/lxsession/LXDE/autostart
        echo '#!/bin/sh -xe\nrm -rf /tmp/* /var/run/xrdp/* && service xrdp start && startx' > /bin/rdp.sh
        chmod +x /bin/rdp.sh
        """
        self._cuisine.core.run_script(C)
