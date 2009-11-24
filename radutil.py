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

"""
from __future__ import with_statement
import re
from contextlib import closing
import sys
import os
from subprocess import Popen, call, STDOUT, PIPE
from sets import Set
import shutil
import uuid

class Config(dict):
    """Example of overloading __getatr__ and __setattr__
    This example creates a dictionary where members can be accessed as attributes
    """
    def __init__(self):
        import ConfigParser
        config_paths = (
            '/etc/radutil.cfg',
            '/usr/local/etc/radutil.cfg',
            '/Library/Preferences/radutil.cfg',
        )
        base_defaults = {
            'rad_dir':'/var/radmind/',
            'default_k_excludes': '',
            'case_sensitive': False,
            'checksum': 'sha1',
            'fsdiffpath': '.',
        }
        configparser = ConfigParser.SafeConfigParser(base_defaults)
        configparser.read(config_paths)
        base_defaults.update(dict(configparser.items('radutil')))
        base_defaults['default_k_excludes'] = base_defaults['default_k_excludes'].split()
        dict.__init__(self, base_defaults)
        self.__initialised = True
        # after initialisation, setting attributes is the same as setting an item

    def __getattr__(self, item):
        """Maps values to attributes.
        Only called if there *isn't* an attribute with this name
        """
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, item, value):
        """Maps attributes to values.
        Only if we are initialised
        """
        if not self.__dict__.has_key('_attrExample__initialised'):  # this test allows attributes to be set in the __init__ method
            return dict.__setattr__(self, item, value)
        elif self.__dict__.has_key(item):       # any normal attributes are handled normally
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)

config = Config()

def is_load(f):
    return f.lower()[-2:] == '.t'

def makedirs(p):
    d = os.path.split(p)[0]
    if not os.path.exists(d):
        os.makedirs(d)

def fs_move(old,new):
    makedirs (new)
    os.rename (old,new)
    
def _rename_or_remove_x_in_k(k,old,new=None,recurse=True,remove=False):
    """internal factored function"""
    mods_made = False
    if new == '':
        # implicit remove
        remove = True
    if not (remove or new):
        raise ValueError ("No replacement name provided")
    for this_k, sub_k, these_t, these_e in walk_K(k):
        if old.lower().endswith('k'):
            subs = sub_k
        elif old.lower().endswith('t'):
            subs = these_t
        if old in subs:
            k_file = get_full_path(this_k)
            f = open(k_file)
            lines = f.readlines()
            if remove:
                lines = [x for x in lines if not old in x]
            else:
                lines = [x.replace(old,new) for x in lines]
            f.close()
            # reopen file with write permission (seeking to 0 could leave stray bytes at the end)
            f = open(k_file,'w')
            f.write(''.join(lines)) # they already have newline
            mods_made = True
            
        if not recurse:
            return mods_made
    return mods_made
    
def rename_t_in_k(k,t_old,t_new,recurse=True):
    """renames occurrences of t in k or children - changes only K files
    
    
    if recurse is false = will only change the file in the k argument - otherwise will 
    traverse any included k files
    
    a new name of '' is an implicit remove
    
    returns true if changes were made
    """
    return _rename_or_remove_x_in_k(k,t_old,new=t_new,recurse=recurse)

def remove_t_in_k(k,t,recurse=True):
    """removes occurrences of t in k or children - changes only K files
    
    if recurse is false = will only change the file in the k argument - otherwise will 
    traverse any included k files
    
    returns true if changes were made
    """
    return _rename_or_remove_x_in_k(k,t,recurse=recurse,remove=True)

def rename_k_in_k(k,k_old,k_new,recurse=True):
    """renames occurrences of k in k or children - changes only K files


    if recurse is false = will only change the file in the k argument - otherwise will 
    traverse any included k files

    a new name of '' is an implicit remove

    returns true if changes were made
    """
    return _rename_or_remove_x_in_k(k,k_old,k_new=k_new,recurse=recurse)

def remove_k_in_k(k,k_old,recurse=True):
    """removes occurrences of k in k or children - changes only K files

    if recurse is false = will only change the file in the k argument - otherwise will 
    traverse any included k files

    returns true if changes were made
    """
    return _rename_or_remove_x_in_k(k,k_old,recurse=recurse,remove=True)


def rename(t,new_name,update_k=True):
    # @@ need to make this generic for T and K files
    """moves or renames transcript/command file and any associated file storage
    
    default is to also do a find and replace of all occurences of old name in command files
    """
    if is_load(t):
        f_dir = get_full_path(t,loc='file')
        new_dir = os.path.join(config.rad_dir,'file',new_name)
        fs_move(f_dir,new_dir)
    t_file = get_full_path(t)
    new_f = os.path.join(config.rad_dir,'transcript',new_name)
    fs_move (t_file,new_f)
    if update_k:
        # update any references to the old name to point to the new name
        swap(t,new_name)

def init_trash():
    # make trash directories
    def make_if_not_exists(p):
        if not os.path.exists(p):
            os.makedirs(p)
            
    trash_dir = os.path.join(config.rad_dir,'trash')
    t = os.path.join(trash_dir,'transcript')
    f = os.path.join(trash_dir,'file')
    k = os.path.join(trash_dir,'command')
    make_if_not_exists(t)
    make_if_not_exists(f)
    make_if_not_exists(k)

def empty_trash():
    shutil.rmtree(os.path.join(config.rad_dir,'trash'))
    init_trash()


def delete(t,update_k=True,multiple_ok=True):
    """deletes a loadset/command and removes references to it from command files"""
    init_trash()
    unique_suffix = ''
    if is_load(t):
        f_dir = get_full_path(t,loc='file')
        new_dir = os.path.join(config.rad_dir,'trash',f_dir.replace(config.rad_dir,''))
        if os.path.exists(new_dir):
            if not multiple_ok:
                raise RuntimeError ("item with that name already in trash")
            else:
                while os.path.exists(new_dir):
                    # @@ this could be substantially improved
                    new_dir += '_'
                    unique_suffix += '_'
        fs_move(f_dir,new_dir)
    # do this in this order just in case files were not found... unlikely
    t_file = get_full_path(t)
    new_f = os.path.join(config.rad_dir,'trash',t_file.replace(config.rad_dir,'')) + unique_suffix
    fs_move(t_file,new_f)
    # @@ clean up empty folders here?
    if update_k:
        # remove any references to the old name
        swap(t,'') 
        
def undelete(t):
    if is_load(t):
        f_dir = get_full_path(t,loc='file',trash=True)
        new_dir = os.path.join(config.rad_dir,f_dir.replace('trash',''))
        fs_move(f_dir,new_dir)
    t_file = get_full_path(t,trash=True)
    new_f = os.path.join(config.rad_dir,t_file.replace('trash',''))
    fs_move(t_file,new_f)

    
def remove_load(t):
    """
    remove all references to a transcript - change only command files
    """
    return swap (t,'')

def remove_command(k):
    """
    remove all references to command file - change only command files
    """
    return swap (k,'')
    
def swap(old,new):
    """
    replace all occurrences of old with new in all command files
    """
    mods_made = False
    for k in all_k():
        r = _rename_or_remove_x_in_k(k,old,new,recurse=False)
        mods_made = mods_made or r
    return mods_made


def all_k(exclude=config.default_k_excludes):
    """lists all k files"""
    # todo - have a global setting for excludes so I can pull my index.K bit
    k_dir = os.path.join(config.rad_dir,'command')
    for root, dirs, files in os.walk(k_dir):
        for f in files:
            if f.lower().endswith('k') and not f in exclude:
                partial = os.path.join(root,f).replace(k_dir,'').lstrip('/')
                yield partial

def sort(f,case_insensitive=True,in_place=True,outfile=None):
    """
    Sorts a transcript
    
    can sort a transcript in place, defaults to being case-insensitive
    
    """
    if not (in_place or outfile):
        # raise exception
        pass
    f = get_full_path(f)
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
    """
    Sums the files listed in a transcript
    
    returns the number of bytes, defaults to number, unless human==True where it returns with human readable label
    
    """
    sum_value = 0
    t_file = get_full_path(T)
    for line in open(t_file):
        if line[0] in ('#','d','l','-'): continue
        data = line.split()
        # print line
        if len(data)>6:
            sum_value = sum_value + int(data[6])
    if human:
        return prettySize(sum_value)
    else:
        return sum_value

def sum_command(K,human=False):
    """
    Sums the files listed in all transcripts referenced by a command file
    
    returns the number of bytes, defaults to number, unless human==True where it returns with human readable label
    
    """
    transcripts = parse_K(K)['transcript']
    sum_value = 0
    for t in transcripts:
        try:
            sum_value = sum_value + sum_transcript(t)
        except:
            print t
            raise
    if human:
        return prettySize(sum_value)
    else:
        return sum_value

def check_t(t):
    # should just be a call to lcksum validate...
    # could use a function to just verify exists
    return not checksums(t)

def check_k(K):
    """
    checks for errors in a command file
    
    checks that a command file, and all descendent command files and transcripts 
    are properly terminated with a carriage return.
    
    checks that every transcript file referenced exists
    
    """
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
            if not check_t(t):
                errors.append ("%s failed to verify" % t)
    return errors
    
def ending_ok(partial):
    """Utility function to check file ends with return"""
    full_path = get_full_path(partial)
    f = open(full_path)
    # go to end of file and read last byte
    f.seek(-1,2)
    ending = f.read(1)
    f.close()
    return ending == '\n'
    
def prettySize(size):
    """convert file size to human readable form"""
    suffixes = [("B",2**10), ("K",2**20), ("M",2**30), ("G",2**40), ("T",2**50)]
    for suf, lim in suffixes:
        if size > lim:
            continue
        else:
            return "%s%s" % (round(size/float(lim/2**10),2),suf)


def get_full_path(partial,loc=False,trash=False,must_exist=True):
    """Utility function to take radmind relative path and resolve to full path"""
    # accept a full path - @@ this aspect needs to go away
    # accepting a full path here will break attempts to get file portion of transcript
    # as it shortcuts any value in loc
    
    # if os.path.exists(partial):
    #     return partial
    
    # this may not be the best way to do it, 
    # but want to provide for path completion when using CLI tool:
    for pre in ('tmp/','transcript/'):
        if partial.startswith(pre):
            partial = partial[len(pre):]
    
    if partial.upper().endswith('.T'):
        sub = loc or 'transcript'
    elif partial.upper().endswith('.K'):
        sub = 'command'
    else:
        raise ValueError("%s not a recognized radmind file type")
    if trash:
        sub = os.path.join('trash',sub)
    full_path = os.path.join(config.rad_dir,sub,partial)
    if not os.path.exists(full_path) and must_exist:
        raise ValueError ("%s %s not found in %s" % (sub,partial,config.rad_dir))
    return full_path

def get_relative_path(partial):
    """simply strips relative path from /var/radmind bash completion"""
    for pre in ('tmp/','transcript/'):
        if partial.startswith(pre):
            partial = partial[len(pre):]
    return partial
    
def find_in_T(pattern,T,escaped=True):
    """
    finds a pattern in a transcript file
    
    Returns a list of tuples of (line number, line)
    pattern is escaped by default
    
    """
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

def find_occurences(item):
    """finds occurrences of t or k in all k files"""
    found_in = []
    item = get_relative_path(item)
    if item.upper().endswith('.T'):
        searching = 'transcript'
    elif item.upper().endswith('.T'):
        searching = 'command'
    else:
        raise ValueError ("%s not a valid radmind file" % item)
    for k in all_k():
        parsed_k = parse_K(k)
        if item in parsed_k[searching]:
            found_in.append(k)
    return found_in
    
def list_pending():
    """
    lists loadsets pending checkin in tmp dir
    """
    return os.listdir(os.path.join(config.rad_dir,'tmp','transcript'))

def checksums(path,update=False,output=sys.stdout,error=sys.stderr):
    cmd = ['lcksum']
    opts = ['-%', '-iq','-c'+config.checksum]
    if not config.case_sensitive:
        opts.append('-I')
    if not update:
        opts.append('-n')
    cmd.extend(opts)
    cmd.append(path)
    process = Popen(' '.join(cmd),shell=True,stdout=output,stderr=error)
    o,e = process.communicate()
    if process.returncode:
        if (update and process.returncode > 1):
            raise RuntimeError ('transcript failed to update')
        elif (not update and process.returncode):
            raise RuntimeError ('transcript failed to verify')
    return process.returncode
    
def checkin(load,update=False,output=sys.stdout,error=sys.stderr):
    """
    checkin an uploaded (lcreate) loadset
    """
    load_transcript = os.path.join(config.rad_dir,'tmp','transcript',load)
    if not os.path.exists (load_transcript):
        raise RuntimeError ('%s not found' % load)
    t_dest = os.path.join(config.rad_dir,'transcript',os.path.basename(load_transcript))
    load_files = os.path.join(config.rad_dir,'tmp','file',load)
    f_dest = os.path.join(config.rad_dir,'file',os.path.basename(load_files))
    if os.path.exists (t_dest) or os.path.exists(f_dest):
        raise RuntimeError ('loadset %s already exists' % load)
    result = checksums (load_transcript,update=update,output=output,error=error)
    shutil.move(load_transcript,t_dest)
    shutil.move(load_files,f_dest)
    return result

def checkin_all(update=False,output=sys.stdout,error=sys.stderr,continue_on_error=True):
    for load in list_pending():
        try:
            checkin (load,update=update,output=output,error=error)         
        except:
            if continue_on_error:
                continue
            else:
                raise


def merge(tlist,dest,delete_combined=True,update_K=True):
    """
    similar to combine, but dest exists
    """
    
    full_dest = get_full_path(dest,must_exist=False)
    if not os.path.exists(full_dest):
        raise RuntimeError ("merge destination does not exist, use combine function instead")
    tmp = 'tmp-%s' % str(uuid.uuid4())
    tlist.append(dest)
    result = combine (tlist,tmp,delete_combined=False,update_K=False)
    if not result:
        delete (dest,update_K=False)
        rename (tmp,dest)
        if update_K:
            tlist.pop()
            # going from passed, to full, to relative is to handle bash completion of transcript/foo.T
            # instead of just foo.T as it would appear in k file
            full_tlist = [get_full_path(t) for t in tlist]
            t_dir = os.path.join(config.rad_dir,'transcript')
            rel_dest = full_dest.replace(t_dir,'').lstrip('/')
            rel_tlist = [t.replace(t_dir,'').lstrip('/') for t in full_tlist]
            modified_k = []
            for k in all_k():
                k_parsed = parse_K(k)
                if dest in k_parsed['transcripts']:
                    for t in rel_tlist:
                            remove_t_in_k (k,t,recurse=False)
                else:
                    for t in rel_tlist:
                        if k not in modified_k:
                            if rename_t_in_k(k,t,rel_dest,recurse=False):
                                modified_k.append(k)
                        else:
                            remove_t_in_k (k,t,recurse=False)
        if delete_combined:
            for t in tlist:
                delete(t,update_k=False)
    return result
    
def combine(tlist,dest,delete_combined=True,update_K=True):
    """
    combine multiple loads into one, and replace occurrences of those transcripts in command files
    
    """
    full_tlist = [get_full_path(t) for t in tlist]
    full_dest = get_full_path(dest,must_exist=False)
    if os.path.exists(full_dest):
        return merge(tlist,dest,delete_combined=delete_combined,update_K=update_K)
        # raise RuntimeError ("Target transcript already exists")
    full_dest_file = get_full_path(dest,loc='file',must_exist=False)
    cmd = ['lmerge']
    if not config.case_sensitive:
        cmd.append('-I')
    cmd.extend(full_tlist)
    cmd.append(full_dest)
    makedirs(full_dest)
    makedirs(full_dest_file)
    result = call(cmd)
    if not result:
        if update_K:
            # relative versions
            t_dir = os.path.join(config.rad_dir,'transcript')
            rel_dest = full_dest.replace(t_dir,'').lstrip('/')
            rel_tlist = [t.replace(t_dir,'').lstrip('/') for t in full_tlist]
            modified_k = []
            for k in all_k():
                for t in rel_tlist:
                    if k not in modified_k:
                        if rename_t_in_k(k,t,rel_dest,recurse=False):
                            modified_k.append(k)
                    else:
                        remove_t_in_k (k,t,recurse=False)
        if delete_combined:
            for t in tlist:
                delete(t,update_k=False)
    return result
                
def find_in_K(pattern,K,escaped=True):
    """find a pattern in any descendent transcript
    
    returns a nested list datastructure for found results:
    [command file name, [
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
    [command file name, [
        transcript1[
            (line number,line),
            (line number,line),
            ],
        transcript2[
            (line number,line),
            (line number,line),
             ]
        ]
    ]]
    
    """
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
    """
    parses a K file to determine all decendent K,T files and any referenced exclude patterns
    
    Will preserve precendence order of transcripts
    
    exclude patterns appearing are filtered to be unique
    
    returns a dictionary of lists {command[],transcript[],exclude[]} 
    
    """
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
                remove = False
                if fields[0] == '-':
                    remove = True
                    del (fields[0])
                path = fields[1]
                if fields[0] in ('p','n'):
                    if path in transcripts:
                        # delete it first then append
                        del(transcripts[transcripts.index(path)])
                    # @@ todo what is the best way to denote negative in this structure without overcomplicating?
                    # perhaps just a '-' prepended - but that has other meaning in k files?
                    if not remove:
                        transcripts.append(path)

                elif fields[0] == 'k':
                    if path in participating_K and not supress_error:
                        # todo custom radmind error exception
                        raise RuntimeError("%s referenced multiple times in %s, possible loop condition" % (path, K))
                    participating_K.append(path)
                    k_parser(get_full_path(path))
                elif fields[0] == 'x':
                    excludes.add(path)
    k_parser(k_file)
    return {'command':list(participating_K),'transcript':list(transcripts),'exclude':list(excludes)}

def parse_K_walked(K,supress_error=False):
    """
    This is probably going away  - see comments
    
    returns a dictionary of {command,transcript,exclude} 
    3 lists: (sub k files, transcripts /unique and ordered by precedence/,exclude patterns)
    """
     # this isnt as usefu as the original parse - because the order of the recursion with a generator doesn't allow
     # keeping the integrity of the transcript order
     # a transcript that appears after a k-in-k can get stomped because the k gets processed after all transcripts
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
    """
    A generator function modeled on os.walk
    
    yields a tuple of (k name, sub k's,transcripts, excludes) for each K traversed
    
    """
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
                remove = False
                if fields[0] == '-':
                    remove = True
                    del (fields[0])
                path = fields[1]
                if fields[0] in ('p','n'):
                    if path in transcripts:
                        # delete it first then append
                        del(transcripts[transcripts.index(path)])
                    # todo what is the best way to denote negative in this structure without overcomplicating?
                    # perhaps just a '-' prepended?
                    if not remove:
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

