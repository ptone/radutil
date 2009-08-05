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

functions to add:
x sort in place
x find file/pattern in T
find file(s) in K (like twhich?)
del loadset (del x.T and file/x.T) find and remove all references to x.T in command files
del file X (search all .T files and delete or comment,and remove from F)
find refrences to T or K that no longer exist and warn/delete
find transcripts that are not used
rename load (renames .T and file and then replaces in K)
find and replace on load with another
twhich+ find pattern not just path
checkin X
check in all (with update or not)
check for ending carriage return
check for circular references in K files
check for all K files referenced in config
check for files in radir/file that are not longer listed in transcript and visversa
split directory into new transcript:
    ie take iphoto themes and factor them into a new transcript

x have some sort of command walk generator function

 - What positively managed items are inside negative directories
(sometimes this is intentional, other times its not)

 - Missing folders in path ( ie /Librarary/foo/bar is defined in a
transcript, but nowhere is /Library/foo defined - can result in
attempts to delete non-empty dirs).

 - What items appear in more than one transcript (like using twhich -a)

 - What positive items will not be applied because they match an
exclude pattern

sum of Transcript or K

- determining which positive items have ACLs/EAs/xattrs and thus may have
difficulty with initial deployment via Radmind. (2123302, 2004112, perhaps
more that I didn't find)

check out fileinput module for checking lines in multiple files
have acces to fileinput.filename(), fileinput.filelineno()

create and apply ACL xattrs special transcript type should used bridged access to ACL functions instead of parsing ls



"""
from __future__ import with_statement
import re
from contextlib import closing
import sys
import os
from subprocess import Popen, call, STDOUT, PIPE
from sets import Set

def sort(f,case_insensitive=True,in_place=True,outfile=None):
    if not (in_place or outfile):
        # raise exception
        pass
    
    # bname = os.path.basename(f)
    if in_place:
        infile = f+'_'
        os.rename(f,infile)
        outfile = f
    else:
        infile = f
    
    cmd = ['lsort']
    if case_insensitive:
        cmd.append('-I')
    cmd.extend(['-o',outfile,infile])
    r = call(cmd)
    if r:
        # todo raise exception here and delete temp
        pass
    if os.path.exists(outfile) and in_place:
        os.remove(infile)

def sum_transcript(T,human=False):
    sum = 0
    t_file = get_full_path(T)
    for line in open(t_file):
        if line[0] in ('#','d','l','-'): continue
        data = line.split()
        # print line
        if len(data)>6:
            sum = sum + int(data[6])
    if human:
        return prettySize(sum)
    else:
        return sum

def sum_command(K,human=False):
    transcripts = parse_K(K)['transcript']
    sum = 0
    for t in transcripts:
        try:
            sum = sum + sum_transcript(t)
        except:
            print t
            raise
    if human:
        return prettySize(sum)
    else:
        return sum

def check_t(T):
    # should just be a call to lcksum validate...
    # could use a function to just verify exists
    pass

def check_k(K):
    parsed = parse_K(K)
    errors = []
    for k in parsed['command']:
        try:
            k_file = get_full_path(k)
        except ValueError,e:
            errors.append(str(e))
        else:
            if not ending_ok(k_file):
                errors.append("%s is not terminated with a carriage return" % k)
    for t in parsed['transcript']:
        try:
            t_file = get_full_path(t)
        except ValueError,e:
            errors.append(str(e))
        else:
            if not ending_ok(t_file):
                errors.append("%s is not terminated with a carriage return" % t)
    return errors
    
def ending_ok(partial):
    full_path = get_full_path(partial)
    f = open(full_path)
    # go to end of file and read last byte
    f.seek(-1,2)
    ending = f.read(1)
    f.close()
    return ending == '\n'
    
def prettySize(size):
    suffixes = [("B",2**10), ("K",2**20), ("M",2**30), ("G",2**40), ("T",2**50)]
    for suf, lim in suffixes:
        if size > lim:
            continue
        else:
            return "%s%s" % (round(size/float(lim/2**10),2),suf)
 
# rad_dir = '/var/radmind/'
rad_dir = '/Users/preston/Projects/san roque/projectsSRS/Radmind/Sample var_radmind/' 

def get_full_path(partial,get_file=False):
    """Utility function to take radmind relative path and resolve to full path"""
    # accept a full path
    if os.path.exists(partial):
        return partial
    if partial.upper().endswith('T'):
        if get_file:
            sub = 'file'
        else:
            sub = 'transcript'
    elif partial.upper().endswith('K'):
        sub = 'command'
    else:
        raise ValueError("%s not a recognized radmind file type")
    full_path = os.path.join(rad_dir,sub,partial)
    if not os.path.exists(full_path):
        raise ValueError ("%s %s not found in %s" % (sub,partial,rad_dir))
    return full_path

def find_in_T(pattern,T,escaped=True):
    """Returns a list of tuples of (line number, line)
    pattern is escaped by default"""
    t_file = get_full_path(T)
    results = []
    if escaped:
        pattern = re.escape(pattern)
    re_pat = re.compile(pattern)
    with closing(open(t_file)) as src:
        for i,line in enumerate(src):
            # if pat in line:
            if re_pat.search(line):
                results.append((i,line))
    return results

def find_in_K(pattern,K,escaped=True):
    """returns a nested list datastructure for found results:
    [command file name [
        transcript1[
            (line number,line),
            (line number,line),
            ],
        transcript2[
            (line number,line),
            (line number,line),
             ]
        ]
    ],
    command file name [
        transcript1[
            (line number,line),
            (line number,line),
            ],
        transcript2[
            (line number,line),
            (line number,line),
             ]
        ]
    ]]"""
    # this might need a total rethink on the return datastructure
    results = []
    for this_k, sub_k, these_t, these_e in walk_K(K):
        found_in = []
        for t in these_t:
            r = find_in_T(pattern,t,escaped = escaped)
            if r:
                found_in.append([t,r])
        if found_in:
            results.append([this_k,found_in])
    return results
    
def __init__():
    pass
    
def main():
    pass

def parse_K(K,supress_error=False):
    """returns a dictionary of {command,transcript,exclude} 
     3 lists: (sub k files, transcripts /unique and ordered by precedence/,exclude patterns)"""
     # see notes in parse_K_walked for why there is so much overlap with this and the walk_K function (this came first)
    k_file = get_full_path(K)
    participating_K = [K]
    transcripts = []
    excludes = Set()
    def k_parser(k_file):
        with closing(open(k_file)) as src:
            for line in src:
                if line == '\n': continue
                if line[0] == '#': continue
                fields = line.split()
                path = fields[1]
                if fields[0] in ('p','n'):
                    if path in transcripts:
                        # delete it first then append
                        del(transcripts[transcripts.index(path)])
                    # todo what is the best way to denote negative in this structure without overcomplicating?
                    # perhaps just a '-' prepended?
                    transcripts.append(path)

                elif fields[0] == 'k':
                    if path in participating_K and not supress_error:
                        # todo custom radmind error exception
                        raise RuntimeError("%s referenced multiple times in %s" % (path, K))
                    participating_K.append(path)
                    k_parser(get_full_path(path))
                elif fields[0] == 'x':
                    excludes.add(path)
    k_parser(k_file)
    return {'command':list(participating_K),'transcript':list(transcripts),'exclude':list(excludes)}

def parse_K_walked(K,supress_error=False):
    # this isnt as usefu as the original parse - because the order of the recursion with a generator doesn't allow
    # keeping the integrity of the transcript order
    # a transcript that appears after a k-in-k can get stomped because the k gets processed after all transcripts
    """returns a dictionary of {command,transcript,exclude} 
     3 lists: (sub k files, transcripts /unique and ordered by precedence/,exclude patterns)"""
    participating_K = []
    transcripts = []
    excludes = Set()
    for this_k, sub_k, these_t, these_e in walk_K(K):
        if this_k != K:
            participating_K.append(this_k)
        for t in these_t:
            if t in transcripts:
                del(transcripts[transcripts.index(t)])
            transcripts.append(t)
        excludes.update(these_e)
    return {'command':list(participating_K),'transcript':list(transcripts),'exclude':list(excludes)}

def walk_K(K):
    """ yields (k name, sub k's,transcripts, excludes)
    similar to os.walk"""
    k_files_to_process = [K]
    seen_k = []
    while k_files_to_process:
        participating_K = []
        transcripts = []
        excludes = Set()
        this_k = k_files_to_process.pop()
        # print this_k
        k_file = get_full_path(this_k)
        with closing(open(k_file)) as src:
            for line in src:
                if line == '\n': continue
                if line[0] == '#': continue
                fields = line.split()
                path = fields[1]
                if fields[0] in ('p','n'):
                    if path in transcripts:
                        # delete it first then append
                        del(transcripts[transcripts.index(path)])
                    # todo what is the best way to denote negative in this structure without overcomplicating?
                    # perhaps just a '-' prepended?
                    transcripts.append(path)
                
                elif fields[0] == 'k':
                    if path in seen_k:
                        raise RuntimeError("%s referenced multiple times in %s" % (path, K))
                    else:
                        seen_k.append(path)
                        participating_K.append(path)
                elif fields[0] == 'x':
                    excludes.add(path)
            if len(participating_K) > 0:
                # print participating_K
                participating_K.reverse()
                k_files_to_process.extend(participating_K)
            yield (this_k,participating_K,transcripts,list(excludes))
            
if __name__ == '__main__':
    main()

