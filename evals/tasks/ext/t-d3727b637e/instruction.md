Duplicated HELO/EHLO
As already mentioned in source code ([链接已移除] also in original smtpd's code) a second HELO/EHLO is rejected but the standart says it should be handled as a RSET command.

Is there any special reason to not allow duplicated HELO/EHLO?  I think the best way is to do the same other SMTP servers do: Allowing a duplicated HELO/EHLO.
Another option is to have a configuration option.
