Load system default SSL cert
This issue applies to the SMTP SSL security mode.  Use the system's default SSL certificate chain.

From https://docs.python.org/3/library/smtplib.html :

> Please use [ssl.SSLContext.load_cert_chain()](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_cert_chain) instead, or let [ssl.create_default_context()](https://docs.python.org/3/library/ssl.html#ssl.create_default_context) select the system’s trusted CA certificates for you.
