#!/usr/bin/env python
# encoding: utf-8
"""

Created by Preston Holmes on 2009-07-22.
preston@ptone.com
Copyright (c) 2009

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Verbs:
delete <t/k>
rename <t/k> new_name
remove <t/k> [k]
swap old new
combine item1 item2 [itemN...] new_name | item_pattern* new_name
bundle item1 item2 [itemN...] bundle_name
checkin
    [update]
    list
    all
    <transcript>
get
    size
    transcripts
    command
"""

vocab = {
    'delete':(delete,['direct']),
    'rename':(rename,['direct','new_name']),
    'remove':(remove,['direct'],['command_file']),
    'swap':(swap,['old','new']),
    'combine':()
}

import sys
import os
from optparse import OptionParser,OptionGroup
import radutil

def delete (t_k):
    radutil.delete(t_k)
    print '%s moved to trash' % t_k
    
def rename (old,new):
    if old.lower()[-2:] == '.t':
        radutil.rename_load (old,new)
        elif radutil.rename_load
def main(argv=None):
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="display all verbose output",default=False)
    # parse options: metavar, default action: store
    parser.usage = """
        help message
    """
    (options, args) = parser.parse_args()
#    if options.some_option != desired_value:
#        parser.error("specified option bad")
    
    # verb needs to be first arg
    verb = args[1]
    if verb.lower() == 'delete'
        del_item = args[2]
        if del_item.lower().endswith('k'):
            radutil.remove_command(del_item)
        elif del_item.lower().endswith('t'):
            radutil.delete_load(del_item)
    
        
if __name__ == "__main__":
    sys.exit(main())
