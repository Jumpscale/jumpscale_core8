JumpScale 8


[![Join the chat at https://gitter.im/Jumpscale/jumpscale_core8](https://badges.gitter.im/Jumpscale/jumpscale_core8.svg)](https://gitter.im/Jumpscale/jumpscale_core8?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


JumpScale is a cloud automation product and a branch from what used to be Pylabs. About 7 years ago Pylabs was the basis of a cloud automation product which was acquired by SUN Microsystems from a company called Q-Layer. In the mean time we are 4 versions further and we have rebranded it to JumpScale.

Please check our [GitBook](https://gig.gitbooks.io/jumpscale-core8/content/) for a full documentation (always shows the master)

- [version & roadmap info](../master/releases.md)

## how to install from master

```
cd $TMPDIR
rm -f install.sh
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/master/install/install.sh?$RANDOM > install.sh
bash install.sh
```


## how to install from a branch

```
cd $TMPDIR
rm -f install.sh
export JSBRANCH="8.1.0"
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$JSBRANCH/install/install.sh?$RANDOM > install.sh
bash install.sh
```
