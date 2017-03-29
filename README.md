JumpScale 8


[![Join the chat at https://gitter.im/Jumpscale/jumpscale_core8](https://badges.gitter.im/Jumpscale/jumpscale_core8.svg)](https://gitter.im/Jumpscale/jumpscale_core8?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


JumpScale is a cloud automation product and a branch from what used to be Pylabs. About 7 years ago Pylabs was the basis of a cloud automation product which was acquired by SUN Microsystems from a company called Q-Layer. In the mean time we are 4 versions further and we have rebranded it to JumpScale.

Please check our [GitBook](https://gig.gitbooks.io/jumpscale-core8/content/) for a full documentation (always shows the master)

- [branches](branches.md)
- [version & roadmap info](../master/releases.md)

## dependencies
Should be executed under root.
```
# pyevn & python 3.6.1
curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash
pyenv install 3.6.1
pyenv shell 3.6.1

```

## how to install from master (THIS IS NOT 8.2.0, DO NOT USE). 
Should be executed under root.

```
cd $TMPDIR
rm -f install.sh
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/master/install/install.sh?$RANDOM > install.sh
bash install.sh
```


## how to install from a branch. 
Should be executed under root.

```
cd $TMPDIR
rm -f install.sh
export JSBRANCH="8.2.0"
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$JSBRANCH/install/install.sh?$RANDOM > install.sh
bash install.sh
```
## how to remove old data

```
curl https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/8.2.0/install/destroy.sh?$RANDOM  | sh
```
